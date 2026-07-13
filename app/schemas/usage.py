"""
用量统计 Schema - Usage Pydantic Schemas
V2预留 - 用于用量统计API
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime, date
from enum import Enum


class TimeRangeEnum(str, Enum):
    """时间范围枚举"""
    TODAY = "today"
    WEEK = "week"
    MONTH = "month"
    CUSTOM = "custom"


class UsageQueryParams(BaseModel):
    """用量查询参数（时间范围、筛选条件）"""
    time_range: TimeRangeEnum = TimeRangeEnum.MONTH
    start_date: Optional[date] = None    # 自定义开始日期
    end_date: Optional[date] = None      # 自定义结束日期
    tool_id: Optional[int] = None        # 按工具筛选
    provider: Optional[str] = None       # 按供应商筛选
    model: Optional[str] = None          # 按模型筛选


class RequestStatsResponse(BaseModel):
    """请求统计响应"""
    total_requests: int = 0              # 总请求数
    success_requests: int = 0            # 成功请求
    error_requests: int = 0              # 异常请求
    success_rate: float = 0.0            # 成功率


class TokenStatsResponse(BaseModel):
    """Token统计响应"""
    total_tokens: int = 0                # 总用量
    month_tokens: int = 0                # 近一个月用量
    today_tokens: int = 0                # 今日用量
    month_change_rate: float = 0.0       # 月环比变化率
    today_change_rate: float = 0.0       # 日环比变化率


class RouteUsageDetailResponse(BaseModel):
    """路由用量详情响应"""
    route_name: str
    model: str
    base_url: str
    is_active: bool = False
    total_tokens: int = 0


class ToolUsageResponse(BaseModel):
    """工具用量响应"""
    tool_id: int
    tool_name: str
    description: str = ""
    route_count: int = 0                 # 路由数量
    request_count: int = 0               # 请求数
    total_tokens: int = 0                # Token总量
    usage_percentage: float = 0.0        # 使用占比
    routes: List[RouteUsageDetailResponse] = []  # 各路由详情


class UsageOverviewResponse(BaseModel):
    """用量总览响应"""
    request_stats: RequestStatsResponse
    token_stats: TokenStatsResponse
    tool_usage: List[ToolUsageResponse]


class DailyUsageResponse(BaseModel):
    """每日用量响应（用于图表）"""
    date: date
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    request_count: int = 0


class UsageTrendResponse(BaseModel):
    """用量趋势响应"""
    daily_usage: List[DailyUsageResponse]
    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0
    total_tokens: int = 0


class UsageRecordResponse(BaseModel):
    """用量记录响应（单条记录详情）"""
    id: int
    user_id: str
    tool_id: int
    tool_name: Optional[str] = None       # 工具名称
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
    request_id: Optional[str] = None
    status: str = "success"
    error_message: Optional[str] = None
    created_at: Optional[datetime] = None


class UsageRecordsListResponse(BaseModel):
    """用量记录列表响应"""
    records: List[UsageRecordResponse]
    total: int                             # 总记录数
    limit: int                             # 每页数量
