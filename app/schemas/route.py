"""
路由 Schema - Route Pydantic Schemas v3.0
用于API请求验证和响应序列化

v3.0 变更: api_type 已移至 Tool 级别，Route Schema 不再包含 api_type
"""
from pydantic import BaseModel
from typing import Optional, Dict


class RouteConfigSchema(BaseModel):
    """路由配置 Schema v3.0 - api_type 已移至 Tool 级别"""
    base_url: str                    # API 基础端点
    model: str                       # 模型名称
    provider_key_name: str           # 引用的密钥名称（供应商）
    order: int = 0                   # 排序字段


class RouteCreate(BaseModel):
    """创建路由请求 v3.0"""
    name: str                        # 路由名称
    base_url: str                    # API 基础端点
    model: str                       # 模型名称
    provider_key_name: str           # 引用的密钥名称（供应商）
    set_active: bool = False         # 是否设为活跃路由
    order: Optional[int] = None      # 排序字段，不传则自动计算
    # api_type 已移至 Tool 级别


class RouteUpdate(BaseModel):
    """更新路由请求 v3.0"""
    base_url: Optional[str] = None
    model: Optional[str] = None
    provider_key_name: Optional[str] = None
    order: Optional[int] = None      # 排序字段
    # api_type 已移至 Tool 级别


class RouteResponse(BaseModel):
    """路由响应 v3.0"""
    name: str
    base_url: str
    model: str
    provider_key_name: str
    is_active: bool = False
    order: int = 0                   # 排序字段
    # api_type 已移至 Tool 级别


class RouteReorderRequest(BaseModel):
    """批量更新路由排序请求"""
    orders: Dict[str, int]           # {route_name: new_order}
