"""
工具模型 - Tool 和 RouteConfig Pydantic 模型
"""
from pydantic import BaseModel, ConfigDict, field_validator
from datetime import datetime
from typing import Optional, Dict, Literal

# API 类型枚举
ApiType = Literal[
    "openai_chat",           # OpenAI Chat Completions API
    "openai_responses",      # OpenAI Responses API
    "anthropic_messages",    # Anthropic Messages API (原生)
    "gemini_generate",       # Google Gemini generateContent API
    "openai_embeddings",     # OpenAI Embeddings API
]


class RouteConfig(BaseModel):
    """路由配置 v3.0 - api_type 已移至 Tool 级别"""
    model_config = ConfigDict(extra='ignore')  # 忽略数据库中旧的 api_type 字段

    base_url: str                    # API 基础端点 (不含具体路径)
    model: str                       # 模型名称
    provider_key_name: str           # 引用的密钥名称（供应商）
    order: int = 0                   # 排序字段，值越小越靠前
    # api_type 已移至 Tool 级别


class Tool(BaseModel):
    """工具模型 v3.0，api_type 提升至 Tool 级别"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: str
    name: str
    description: str = ""            # 工具描述
    token_hash: str
    api_type: ApiType = "openai_chat"  # v3.0: Tool 级别的 API 类型
    active_route_name: Optional[str] = None
    routes: Dict[str, RouteConfig] = {}
    status: int = 1
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    @field_validator('api_type', mode='before')
    @classmethod
    def set_default_api_type(cls, v):
        """如果 api_type 为 None 或不存在，设置默认值"""
        if v is None:
            return "openai_chat"
        return v
