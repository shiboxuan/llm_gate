"""
Token用量模型 - V2预留
包含用量记录和统计相关的 Pydantic 模型

数据库表设计:
- usage_records_YYYY: 用量明细分表（每年一个独立表，如 usage_records_2026）
- user_usage_summary: 用户用量汇总表（累计总量，避免跨分表聚合）

分表策略:
- 写入时根据 created_at 时间戳确定写入哪个分表
- 查询时根据时间范围确定需要查询哪些分表
- 全量统计从 user_usage_summary 汇总表获取，避免跨分表扫描
"""
from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import Optional, List


class UserUsageSummary(BaseModel):
    """用户用量汇总（轻量汇总表，存储累计总量）
    
    用于避免跨分区计算累计值，每次记录用量时同步更新
    """
    model_config = ConfigDict(from_attributes=True)
    
    user_id: str                          # 用户ID（主键）
    total_tokens: int = 0                 # 累计总Token数
    success_requests: int = 0             # 累计成功请求数
    error_requests: int = 0               # 累计异常请求数
    updated_at: Optional[datetime] = None


class UsageRecord(BaseModel):
    """单条用量记录"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: str
    tool_id: int
    route_name: str
    provider_key_name: str
    model: str
    base_url: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    # Anthropic cache tokens（OpenAI 等其他 provider 默认为 0）
    cache_creation_input_tokens: int = 0
    cache_read_input_tokens: int = 0
    # OpenAI cache tokens（Anthropic 等其他 provider 默认为 0）
    cached_tokens: int = 0
    request_id: Optional[str] = None
    api_type: Optional[str] = None  # v2.0 新增：API 类型（openai_chat/anthropic_messages/gemini_generate 等）
    status: str = "success"
    error_message: Optional[str] = None
    created_at: Optional[datetime] = None


class RequestStats(BaseModel):
    """请求统计"""
    total_requests: int = 0           # 总请求数
    success_requests: int = 0         # 成功请求
    error_requests: int = 0           # 异常请求
    success_rate: float = 0.0         # 成功率


class TokenStats(BaseModel):
    """Token统计"""
    total_tokens: int = 0             # 总用量
    month_tokens: int = 0             # 近一个月用量
    today_tokens: int = 0             # 今日用量
    month_change_rate: float = 0.0    # 月环比变化率
    today_change_rate: float = 0.0    # 日环比变化率


class RouteUsageDetail(BaseModel):
    """路由用量详情"""
    route_name: str
    model: str
    base_url: str
    is_active: bool = False
    total_tokens: int = 0


class ToolUsageStats(BaseModel):
    """工具用量统计"""
    tool_id: int
    tool_name: str
    description: str = ""
    route_count: int = 0              # 路由数量
    request_count: int = 0            # 请求数
    total_tokens: int = 0             # Token总量
    usage_percentage: float = 0.0     # 使用占比
    routes: List[RouteUsageDetail] = []  # 各路由详情


class UsageOverview(BaseModel):
    """用量总览（V2统计页面数据结构）"""
    request_stats: RequestStats
    token_stats: TokenStats
    tool_usage: List[ToolUsageStats]
