"""
Token 用量统计服务

提供用量记录、查询、统计等功能：
- 记录单次请求的 Token 用量
- 获取请求统计、Token 统计
- 获取按工具分类的用量统计
- 计算环比变化率
- Redis 缓存热点数据优化

使用 SQLAlchemy 2.0 async 直连 PostgreSQL，usage_records 为单表（按 created_at 索引查询）。
"""
import json
from datetime import datetime, timedelta
from typing import List, Optional

from redis.asyncio import Redis
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_current_time
from app.db.orm import ToolORM, UsageRecordORM, UserUsageSummaryORM
from app.db.session import get_session_factory
from app.models.usage import (
    RequestStats,
    RouteUsageDetail,
    TokenStats,
    ToolUsageStats,
    UsageOverview,
    UsageRecord,
    UserUsageSummary,
)


class UsageService:
    """Token 用量统计服务"""

    def __init__(self, session: AsyncSession):
        """初始化用量统计服务

        Args:
            session: 数据库异步会话（用于查询统计；record_usage 内部自建独立 session）
        """
        self.session = session

    async def record_usage(self, usage_data: dict) -> UsageRecord:
        """记录单次请求的 Token 用量

        可能在 background task 中调用（请求已结束、self.session 已关闭），
        因此内部使用独立 session 执行写入。

        Args:
            usage_data: 用量数据，包含 user_id/tool_id/route_name/provider_key_name/model/base_url/prompt_tokens/completion_tokens/total_tokens 等

        Returns:
            UsageRecord: 创建的用量记录
        """
        usage_data.setdefault("status", "success")
        usage_data.setdefault("request_id", None)
        usage_data.setdefault("error_message", None)

        record = UsageRecordORM(
            user_id=usage_data["user_id"],
            tool_id=usage_data["tool_id"],
            route_name=usage_data.get("route_name", ""),
            provider_key_name=usage_data.get("provider_key_name") or usage_data.get("provider", ""),
            model=usage_data.get("model", ""),
            base_url=usage_data.get("base_url", ""),
            prompt_tokens=usage_data.get("prompt_tokens", 0),
            completion_tokens=usage_data.get("completion_tokens", 0),
            total_tokens=usage_data.get("total_tokens", 0),
            cache_creation_input_tokens=usage_data.get("cache_creation_input_tokens", 0),
            cache_read_input_tokens=usage_data.get("cache_read_input_tokens", 0),
            cached_tokens=usage_data.get("cached_tokens", 0),
            request_id=usage_data.get("request_id"),
            api_type=usage_data.get("api_type"),
            status=usage_data.get("status", "success"),
            error_message=usage_data.get("error_message"),
        )

        # 使用独立 session，兼容 background task 调用场景
        session_factory = get_session_factory()
        async with session_factory() as session:
            session.add(record)
            await session.commit()
            await session.refresh(record)
            await self._update_user_summary(session, record.user_id, record.total_tokens, record.status == "success")
            result = self._orm_to_record(record)
        return result

    async def _update_user_summary(self, session: AsyncSession, user_id: str, total_tokens: int, is_success: bool) -> None:
        """更新用户用量汇总表（upsert，保证原子性）

        Args:
            session: 数据库会话
            user_id: 用户ID
            total_tokens: 本次请求的 Token 数
            is_success: 是否成功请求
        """
        now = get_current_time()
        success_inc = 1 if is_success else 0
        error_inc = 0 if is_success else 1
        stmt = pg_insert(UserUsageSummaryORM).values(
            user_id=user_id,
            total_tokens=total_tokens,
            success_requests=success_inc,
            error_requests=error_inc,
            updated_at=now,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=[UserUsageSummaryORM.user_id],
            set_={
                "total_tokens": UserUsageSummaryORM.total_tokens + total_tokens,
                "success_requests": UserUsageSummaryORM.success_requests + success_inc,
                "error_requests": UserUsageSummaryORM.error_requests + error_inc,
                "updated_at": now,
            },
        )
        await session.execute(stmt)
        await session.commit()

    async def get_user_summary(self, user_id: str) -> Optional[UserUsageSummary]:
        """获取用户用量汇总"""
        result = await self.session.execute(
            select(UserUsageSummaryORM).where(UserUsageSummaryORM.user_id == user_id)
        )
        orm = result.scalar_one_or_none()
        if not orm:
            return None
        summary = UserUsageSummary(user_id=orm.user_id, total_tokens=orm.total_tokens, success_requests=orm.success_requests, error_requests=orm.error_requests, updated_at=orm.updated_at)
        return summary

    async def get_request_stats(self, user_id: str, start_time: Optional[datetime] = None, end_time: Optional[datetime] = None) -> RequestStats:
        """获取请求统计

        - 全量统计从 user_usage_summary 汇总表获取
        - 有时间范围时从 usage_records 查询
        """
        # 全量：从汇总表获取
        if start_time is None and end_time is None:
            summary = await self.get_user_summary(user_id)
            if summary:
                total = summary.success_requests + summary.error_requests
                success_rate = round(summary.success_requests / total * 100, 2) if total > 0 else 0.0
                stats = RequestStats(total_requests=total, success_requests=summary.success_requests, error_requests=summary.error_requests, success_rate=success_rate)
                return stats
            stats = RequestStats()
            return stats

        # 有时间范围：从 usage_records 查询
        if end_time is None:
            end_time = get_current_time()

        result = await self.session.execute(
            select(UsageRecordORM.status, func.count().label("cnt"))
            .where(UsageRecordORM.user_id == user_id, UsageRecordORM.created_at.between(start_time, end_time))
            .group_by(UsageRecordORM.status)
        )
        rows = result.all()
        total = sum(r[1] for r in rows)
        success = sum(r[1] for r in rows if r[0] == "success")
        error = sum(r[1] for r in rows if r[0] == "error")
        success_rate = round(success / total * 100, 2) if total > 0 else 0.0
        stats = RequestStats(total_requests=total, success_requests=success, error_requests=error, success_rate=success_rate)
        return stats

    async def get_token_stats(self, user_id: str) -> TokenStats:
        """获取 Token 统计（总量、月用量、日用量、环比变化率）"""
        now = get_current_time()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        yesterday_start = today_start - timedelta(days=1)
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        last_month_start = (month_start - timedelta(days=1)).replace(day=1)

        # 总量从汇总表获取
        summary = await self.get_user_summary(user_id)
        total_tokens = summary.total_tokens if summary else 0

        # 月/日用量从 usage_records 求和
        month_tokens = await self._sum_tokens(user_id, month_start, now)
        last_month_tokens = await self._sum_tokens(user_id, last_month_start, month_start)
        today_tokens = await self._sum_tokens(user_id, today_start, now)
        yesterday_tokens = await self._sum_tokens(user_id, yesterday_start, today_start)

        month_change_rate = self.calculate_change_rate(month_tokens, last_month_tokens)
        today_change_rate = self.calculate_change_rate(today_tokens, yesterday_tokens)
        stats = TokenStats(total_tokens=total_tokens, month_tokens=month_tokens, today_tokens=today_tokens, month_change_rate=month_change_rate, today_change_rate=today_change_rate)
        return stats

    async def _sum_tokens(self, user_id: str, start_time: datetime, end_time: datetime) -> int:
        """求和指定时间范围内的 total_tokens"""
        result = await self.session.execute(
            select(func.coalesce(func.sum(UsageRecordORM.total_tokens), 0))
            .where(UsageRecordORM.user_id == user_id, UsageRecordORM.created_at.between(start_time, end_time))
        )
        total = result.scalar() or 0
        return total

    async def get_tool_usage_stats(self, user_id: str, start_time: Optional[datetime] = None, end_time: Optional[datetime] = None) -> List[ToolUsageStats]:
        """获取按工具分类的用量统计"""
        if end_time is None:
            end_time = get_current_time()
        if start_time is None:
            start_time = datetime(2020, 1, 1, tzinfo=get_current_time().tzinfo)

        # 按 tool_id 分组统计
        result = await self.session.execute(
            select(
                UsageRecordORM.tool_id,
                func.coalesce(func.sum(UsageRecordORM.total_tokens), 0).label("total_tokens"),
                func.count().label("request_count"),
            )
            .where(UsageRecordORM.user_id == user_id, UsageRecordORM.created_at.between(start_time, end_time))
            .group_by(UsageRecordORM.tool_id)
        )
        groups = result.all()

        # 获取用户所有工具
        tools_result = await self.session.execute(select(ToolORM).where(ToolORM.user_id == user_id))
        tools = tools_result.scalars().all()
        tools_map = {t.id: t for t in tools}

        total_all_tokens = sum(g[1] or 0 for g in groups)

        stats_list = []
        for g in groups:
            tool_id = g[0]
            tool_tokens = g[1] or 0
            request_count = g[2]
            tool = tools_map.get(tool_id)
            usage_percentage = round(tool_tokens / total_all_tokens * 100, 2) if total_all_tokens > 0 else 0.0
            routes = await self._get_route_usage_details(user_id, tool_id, start_time, end_time)
            stats = ToolUsageStats(tool_id=tool_id, tool_name=tool.name if tool else "Unknown", description=tool.description if tool else "", route_count=len(routes), request_count=request_count, total_tokens=tool_tokens, usage_percentage=usage_percentage, routes=routes)
            stats_list.append(stats)

        stats_list.sort(key=lambda x: x.total_tokens, reverse=True)
        return stats_list

    async def _get_route_usage_details(self, user_id: str, tool_id: int, start_time: datetime, end_time: datetime) -> List[RouteUsageDetail]:
        """获取工具下各路由的用量详情"""
        result = await self.session.execute(
            select(
                UsageRecordORM.route_name,
                UsageRecordORM.model,
                UsageRecordORM.base_url,
                func.coalesce(func.sum(UsageRecordORM.total_tokens), 0).label("total_tokens"),
            )
            .where(UsageRecordORM.user_id == user_id, UsageRecordORM.tool_id == tool_id, UsageRecordORM.created_at.between(start_time, end_time))
            .group_by(UsageRecordORM.route_name, UsageRecordORM.model, UsageRecordORM.base_url)
        )
        rows = result.all()
        routes = []
        for r in rows:
            route = RouteUsageDetail(route_name=r[0], model=r[1], base_url=r[2], is_active=True, total_tokens=r[3] or 0)
            routes.append(route)
        routes.sort(key=lambda x: x.total_tokens, reverse=True)
        return routes

    async def get_usage_overview(self, user_id: str, start_time: Optional[datetime] = None, end_time: Optional[datetime] = None) -> UsageOverview:
        """获取用量总览（统计页面完整数据）"""
        request_stats = await self.get_request_stats(user_id, start_time, end_time)
        token_stats = await self.get_token_stats(user_id)
        tool_usage = await self.get_tool_usage_stats(user_id, start_time, end_time)
        overview = UsageOverview(request_stats=request_stats, token_stats=token_stats, tool_usage=tool_usage)
        return overview

    async def get_tool_routes_usage(self, user_id: str, tool_id: int, start_time: Optional[datetime] = None, end_time: Optional[datetime] = None) -> List[RouteUsageDetail]:
        """获取指定工具的路由用量详情"""
        if end_time is None:
            end_time = get_current_time()
        if start_time is None:
            start_time = datetime(2020, 1, 1, tzinfo=get_current_time().tzinfo)
        routes = await self._get_route_usage_details(user_id, tool_id, start_time, end_time)
        return routes

    async def get_recent_usage_records(self, user_id: str, limit: int = 10, tool_id: Optional[int] = None) -> tuple[List[dict], int]:
        """获取用户最近 n 条用量记录

        Returns:
            tuple: (用量记录列表, 总记录数)
        """
        limit = min(limit, 100)

        # 查询总数
        count_stmt = select(func.count()).select_from(UsageRecordORM).where(UsageRecordORM.user_id == user_id)
        if tool_id is not None:
            count_stmt = count_stmt.where(UsageRecordORM.tool_id == tool_id)
        count_result = await self.session.execute(count_stmt)
        total_count = count_result.scalar() or 0

        # 查询记录（按 created_at 倒序）
        stmt = select(UsageRecordORM).where(UsageRecordORM.user_id == user_id)
        if tool_id is not None:
            stmt = stmt.where(UsageRecordORM.tool_id == tool_id)
        stmt = stmt.order_by(UsageRecordORM.created_at.desc()).limit(limit)
        result = await self.session.execute(stmt)
        records_orm = result.scalars().all()

        # 转换为 dict 列表（保持原返回格式）
        records = []
        for r in records_orm:
            record = {
                "id": r.id, "user_id": r.user_id, "tool_id": r.tool_id,
                "route_name": r.route_name, "provider_key_name": r.provider_key_name,
                "model": r.model, "base_url": r.base_url,
                "prompt_tokens": r.prompt_tokens, "completion_tokens": r.completion_tokens,
                "total_tokens": r.total_tokens,
                "cache_creation_input_tokens": r.cache_creation_input_tokens,
                "cache_read_input_tokens": r.cache_read_input_tokens,
                "cached_tokens": r.cached_tokens,
                "request_id": r.request_id, "api_type": r.api_type,
                "status": r.status, "error_message": r.error_message,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            records.append(record)

        # 填充 tool_name
        if records:
            tool_ids = list(set(r["tool_id"] for r in records if r.get("tool_id")))
            if tool_ids:
                tools_map = await self._get_tools_map(user_id, tool_ids)
                for record in records:
                    tid = record.get("tool_id")
                    if tid and tid in tools_map:
                        record["tool_name"] = tools_map[tid].get("name", "")

        return records, total_count

    async def _get_tools_map(self, user_id: str, tool_ids: List[int]) -> dict:
        """获取工具ID到工具信息的映射"""
        result = await self.session.execute(
            select(ToolORM).where(ToolORM.user_id == user_id, ToolORM.id.in_(tool_ids))
        )
        tools = result.scalars().all()
        tools_map = {t.id: {"id": t.id, "name": t.name, "description": t.description} for t in tools}
        return tools_map

    def _orm_to_record(self, orm: UsageRecordORM) -> UsageRecord:
        """ORM 转 Pydantic"""
        record = UsageRecord(
            id=orm.id, user_id=orm.user_id, tool_id=orm.tool_id,
            route_name=orm.route_name, provider_key_name=orm.provider_key_name,
            model=orm.model, base_url=orm.base_url,
            prompt_tokens=orm.prompt_tokens, completion_tokens=orm.completion_tokens,
            total_tokens=orm.total_tokens,
            cache_creation_input_tokens=orm.cache_creation_input_tokens,
            cache_read_input_tokens=orm.cache_read_input_tokens,
            cached_tokens=orm.cached_tokens,
            request_id=orm.request_id, api_type=orm.api_type,
            status=orm.status, error_message=orm.error_message,
            created_at=orm.created_at,
        )
        return record

    def calculate_change_rate(self, current: int, previous: int) -> float:
        """计算环比变化率（百分比）"""
        if previous == 0:
            rate = 100.0 if current > 0 else 0.0
            return rate
        rate = round((current - previous) / previous * 100, 2)
        return rate


class UsageCacheService:
    """用量统计缓存服务

    提供用量总览的 Redis 缓存读写操作
    """

    def __init__(self, redis: Redis, usage_service: UsageService):
        """初始化用量缓存服务

        Args:
            redis: Redis 客户端
            usage_service: 用量统计服务
        """
        self.redis = redis
        self.usage_service = usage_service
        self.prefix = "usage_overview:"
        self.default_ttl = 60  # 默认缓存60秒

    async def get_cached_usage_overview(self, user_id: str) -> Optional[UsageOverview]:
        """从缓存获取用量总览"""
        key = f"{self.prefix}{user_id}"
        data = await self.redis.get(key)
        if data:
            parsed = json.loads(data)
            request_stats = RequestStats(**parsed["request_stats"])
            token_stats = TokenStats(**parsed["token_stats"])
            tool_usage = []
            for tu in parsed["tool_usage"]:
                routes = []
                for r in tu.get("routes", []):
                    route = RouteUsageDetail(**r)
                    routes.append(route)
                tool = ToolUsageStats(tool_id=tu["tool_id"], tool_name=tu["tool_name"], description=tu.get("description") or "", route_count=tu.get("route_count", 0), request_count=tu.get("request_count", 0), total_tokens=tu.get("total_tokens", 0), usage_percentage=tu.get("usage_percentage", 0.0), routes=routes)
                tool_usage.append(tool)
            overview = UsageOverview(request_stats=request_stats, token_stats=token_stats, tool_usage=tool_usage)
            return overview
        return None

    async def cache_usage_overview(self, user_id: str, overview: UsageOverview, ttl: int = None) -> None:
        """缓存用量总览"""
        key = f"{self.prefix}{user_id}"
        cache_ttl = ttl or self.default_ttl

        # 序列化为 JSON
        data = {
            "request_stats": {"total_requests": overview.request_stats.total_requests, "success_requests": overview.request_stats.success_requests, "error_requests": overview.request_stats.error_requests, "success_rate": overview.request_stats.success_rate},
            "token_stats": {"total_tokens": overview.token_stats.total_tokens, "month_tokens": overview.token_stats.month_tokens, "today_tokens": overview.token_stats.today_tokens, "month_change_rate": overview.token_stats.month_change_rate, "today_change_rate": overview.token_stats.today_change_rate},
            "tool_usage": []
        }
        for tu in overview.tool_usage:
            routes = []
            for r in tu.routes:
                route_dict = {"route_name": r.route_name, "model": r.model, "base_url": r.base_url, "is_active": r.is_active, "total_tokens": r.total_tokens}
                routes.append(route_dict)
            tool_dict = {"tool_id": tu.tool_id, "tool_name": tu.tool_name, "description": tu.description, "route_count": tu.route_count, "request_count": tu.request_count, "total_tokens": tu.total_tokens, "usage_percentage": tu.usage_percentage, "routes": routes}
            data["tool_usage"].append(tool_dict)

        await self.redis.setex(key, cache_ttl, json.dumps(data))

    async def invalidate_usage_cache(self, user_id: str) -> None:
        """使用量缓存失效"""
        key = f"{self.prefix}{user_id}"
        await self.redis.delete(key)

    async def get_usage_overview_with_cache(self, user_id: str, start_time: Optional[datetime] = None, end_time: Optional[datetime] = None) -> UsageOverview:
        """获取用量总览（优先从缓存获取）"""
        # 只有默认时间范围才使用缓存
        if start_time is None and end_time is None:
            cached = await self.get_cached_usage_overview(user_id)
            if cached:
                return cached

        # 缓存未命中，从数据库获取
        overview = await self.usage_service.get_usage_overview(user_id, start_time, end_time)

        # 只有默认时间范围才缓存
        if start_time is None and end_time is None:
            await self.cache_usage_overview(user_id, overview)

        return overview
