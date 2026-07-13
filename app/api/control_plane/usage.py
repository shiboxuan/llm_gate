"""
用量统计路由 - V2预留

提供用量总览、请求统计、Token统计、按工具分类的用量统计等功能
"""
from typing import List
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Query, Path

from app.core.dependencies import get_current_user, get_usage_service, get_usage_cache_service
from app.schemas.usage import UsageOverviewResponse, RequestStatsResponse, TokenStatsResponse, ToolUsageResponse, RouteUsageDetailResponse, UsageRecordResponse, UsageRecordsListResponse
from app.services.usage_service import UsageService, UsageCacheService
from app.config import get_current_time

router = APIRouter()


def _parse_time_filter(time_filter: str) -> tuple:
    """
    解析时间过滤器，返回 (start_time, end_time)
    
    Args:
        time_filter: 时间过滤器字符串 (all, today, week, month)
        
    Returns:
        tuple: (start_time, end_time)
    """
    now = get_current_time()
    end_time = now
    
    if time_filter == "today":
        start_time = now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif time_filter == "week":
        start_time = now - timedelta(days=7)
    elif time_filter == "month":
        start_time = now - timedelta(days=30)
    else:  # "all"
        start_time = None
        end_time = None
    
    result = (start_time, end_time)
    return result


@router.get("/overview", response_model=UsageOverviewResponse)
async def get_usage_overview(time_filter: str = Query("month", enum=["all", "today", "week", "month"]), current_user=Depends(get_current_user), usage_service: UsageService = Depends(get_usage_service)) -> UsageOverviewResponse:
    """获取用量总览"""
    start_time, end_time = _parse_time_filter(time_filter)
    overview = await usage_service.get_usage_overview(current_user.id, start_time, end_time)
    
    # 转换为响应格式
    request_stats = RequestStatsResponse(total_requests=overview.request_stats.total_requests, success_requests=overview.request_stats.success_requests, error_requests=overview.request_stats.error_requests, success_rate=overview.request_stats.success_rate)
    
    token_stats = TokenStatsResponse(total_tokens=overview.token_stats.total_tokens, month_tokens=overview.token_stats.month_tokens, today_tokens=overview.token_stats.today_tokens, month_change_rate=overview.token_stats.month_change_rate, today_change_rate=overview.token_stats.today_change_rate)
    
    tool_usage = []
    for tu in overview.tool_usage:
        routes = []
        for r in tu.routes:
            route_detail = RouteUsageDetailResponse(route_name=r.route_name, model=r.model, base_url=r.base_url, is_active=r.is_active, total_tokens=r.total_tokens)
            routes.append(route_detail)
        tool = ToolUsageResponse(tool_id=tu.tool_id, tool_name=tu.tool_name, description=tu.description, route_count=tu.route_count, request_count=tu.request_count, total_tokens=tu.total_tokens, usage_percentage=tu.usage_percentage, routes=routes)
        tool_usage.append(tool)
    
    response = UsageOverviewResponse(request_stats=request_stats, token_stats=token_stats, tool_usage=tool_usage)
    return response


@router.get("/requests", response_model=RequestStatsResponse)
async def get_request_stats(time_filter: str = Query("month", enum=["all", "today", "week", "month"]), current_user=Depends(get_current_user), usage_service: UsageService = Depends(get_usage_service)) -> RequestStatsResponse:
    """获取请求统计"""
    start_time, end_time = _parse_time_filter(time_filter)
    stats = await usage_service.get_request_stats(current_user.id, start_time, end_time)
    
    response = RequestStatsResponse(total_requests=stats.total_requests, success_requests=stats.success_requests, error_requests=stats.error_requests, success_rate=stats.success_rate)
    return response


@router.get("/tokens", response_model=TokenStatsResponse)
async def get_token_stats(current_user=Depends(get_current_user), usage_service: UsageService = Depends(get_usage_service)) -> TokenStatsResponse:
    """获取Token统计"""
    stats = await usage_service.get_token_stats(current_user.id)
    
    response = TokenStatsResponse(total_tokens=stats.total_tokens, month_tokens=stats.month_tokens, today_tokens=stats.today_tokens, month_change_rate=stats.month_change_rate, today_change_rate=stats.today_change_rate)
    return response


@router.get("/tools", response_model=List[ToolUsageResponse])
async def get_tool_usage(time_filter: str = Query("month", enum=["all", "today", "week", "month"]), current_user=Depends(get_current_user), usage_service: UsageService = Depends(get_usage_service)) -> List[ToolUsageResponse]:
    """获取按工具分类的用量统计"""
    start_time, end_time = _parse_time_filter(time_filter)
    stats_list = await usage_service.get_tool_usage_stats(current_user.id, start_time, end_time)
    
    response = []
    for tu in stats_list:
        routes = []
        for r in tu.routes:
            route_detail = RouteUsageDetailResponse(route_name=r.route_name, model=r.model, base_url=r.base_url, is_active=r.is_active, total_tokens=r.total_tokens)
            routes.append(route_detail)
        tool = ToolUsageResponse(tool_id=tu.tool_id, tool_name=tu.tool_name, description=tu.description, route_count=tu.route_count, request_count=tu.request_count, total_tokens=tu.total_tokens, usage_percentage=tu.usage_percentage, routes=routes)
        response.append(tool)
    return response


@router.get("/tools/{tool_id}/routes", response_model=List[RouteUsageDetailResponse])
async def get_tool_routes_usage(tool_id: int = Path(..., description="工具ID"), time_filter: str = Query("month", enum=["all", "today", "week", "month"]), current_user=Depends(get_current_user), usage_service: UsageService = Depends(get_usage_service)) -> List[RouteUsageDetailResponse]:
    """获取指定工具的路由用量详情"""
    start_time, end_time = _parse_time_filter(time_filter)
    routes = await usage_service.get_tool_routes_usage(current_user.id, tool_id, start_time, end_time)
    
    response = []
    for r in routes:
        route_detail = RouteUsageDetailResponse(route_name=r.route_name, model=r.model, base_url=r.base_url, is_active=r.is_active, total_tokens=r.total_tokens)
        response.append(route_detail)
    return response


@router.get("/records", response_model=UsageRecordsListResponse)
async def get_recent_usage_records(
    limit: int = Query(10, ge=1, le=100, description="返回记录数量，默认10条，最大100条"),
    tool_id: int = Query(None, description="工具ID，可选，用于过滤特定工具的记录"),
    current_user=Depends(get_current_user),
    usage_service: UsageService = Depends(get_usage_service)
) -> UsageRecordsListResponse:
    """
    获取用户最近的用量记录
    
    根据当前用户的 token 获取其最近 n 条用量记录，支持按工具过滤。
    记录按创建时间倒序排列，最新的记录排在前面。
    
    - **limit**: 返回记录数量，范围 1-100，默认 10
    - **tool_id**: 工具ID（可选），用于过滤特定工具的用量记录
    """
    records, total = await usage_service.get_recent_usage_records(
        user_id=current_user.id,
        limit=limit,
        tool_id=tool_id
    )
    
    # 转换为响应格式
    response_records = []
    for record in records:
        response_record = UsageRecordResponse(
            id=record.get("id"),
            user_id=record.get("user_id"),
            tool_id=record.get("tool_id"),
            tool_name=record.get("tool_name"),
            route_name=record.get("route_name", ""),
            provider_key_name=record.get("provider_key_name", ""),
            model=record.get("model", ""),
            base_url=record.get("base_url", ""),
            prompt_tokens=record.get("prompt_tokens", 0),
            completion_tokens=record.get("completion_tokens", 0),
            total_tokens=record.get("total_tokens", 0),
            cache_creation_input_tokens=record.get("cache_creation_input_tokens", 0),
            cache_read_input_tokens=record.get("cache_read_input_tokens", 0),
            request_id=record.get("request_id"),
            status=record.get("status", "success"),
            error_message=record.get("error_message"),
            created_at=record.get("created_at")
        )
        response_records.append(response_record)
    
    response = UsageRecordsListResponse(
        records=response_records,
        total=total,
        limit=limit
    )
    return response
