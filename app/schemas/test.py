"""
连接测试 Schema - 连通性测试请求和响应模型
"""
from typing import Optional, Literal, List, Any

from pydantic import BaseModel, Field

from app.models.tool import ApiType


class ConnectionTestRequest(BaseModel):
    """连接测试请求"""
    api_type: ApiType = Field(..., description="API 类型")
    base_url: str = Field(..., min_length=1, description="API 基础 URL")
    model: str = Field(..., min_length=1, description="模型名称")
    provider_key_name: str = Field(..., min_length=1, description="Provider Key 名称")


class ConnectionTestResponse(BaseModel):
    """连接测试响应"""
    success: bool = Field(..., description="测试是否成功")
    message: str = Field(..., description="测试结果消息")
    latency_ms: Optional[int] = Field(None, description="响应耗时（毫秒）")
    error_code: Optional[str] = Field(None, description="错误码（失败时）")
    details: Optional[str] = Field(None, description="详细错误信息（失败时）")


# ==================== 模型探测 Schema ====================

class ModelsProbeItem(BaseModel):
    """单个探测目标"""
    base_url: str = Field(..., min_length=1, description="API 基础 URL")
    provider_key_name: str = Field(..., min_length=1, description="Provider Key 名称")


class ModelsProbeRequest(BaseModel):
    """模型探测请求（批量）"""
    targets: List[ModelsProbeItem] = Field(..., min_length=1, description="探测目标列表")


class ModelsProbeResultItem(BaseModel):
    """单个探测结果"""
    base_url: str = Field(..., description="探测的 base_url")
    success: bool = Field(..., description="探测是否成功")
    message: str = Field(..., description="结果消息")
    latency_ms: Optional[int] = Field(None, description="响应耗时（毫秒）")
    data: Optional[Any] = Field(None, description="原始响应数据")
    error_code: Optional[str] = Field(None, description="错误码（失败时）")


class ModelsProbeResponse(BaseModel):
    """模型探测响应（批量）"""
    results: List[ModelsProbeResultItem] = Field(..., description="各目标探测结果")
