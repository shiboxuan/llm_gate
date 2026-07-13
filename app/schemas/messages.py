"""
Messages Schema - Anthropic Messages API Pydantic Schemas
兼容 Anthropic Claude API 格式，适用于 Claude Code 等工具
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any, Union


# ============ 请求相关 Schema ============

class TextContent(BaseModel):
    """文本内容块"""
    type: str = "text"
    text: str


class ImageSource(BaseModel):
    """图片来源"""
    type: str = "base64"
    media_type: str
    data: str


class ImageContent(BaseModel):
    """图片内容块"""
    type: str = "image"
    source: ImageSource


class ToolUseContent(BaseModel):
    """工具使用内容块"""
    type: str = "tool_use"
    id: str
    name: str
    input: Dict[str, Any]


class ToolResultContent(BaseModel):
    """工具结果内容块"""
    type: str = "tool_result"
    tool_use_id: str
    content: Optional[Union[str, List[Dict[str, Any]]]] = None
    is_error: Optional[bool] = None


# 内容块类型
ContentBlock = Union[TextContent, ImageContent, ToolUseContent, ToolResultContent, Dict[str, Any]]


class AnthropicMessage(BaseModel):
    """Anthropic 消息结构"""
    role: str  # user, assistant
    content: Union[str, List[ContentBlock]]


class ToolDefinition(BaseModel):
    """工具定义 - 支持自定义工具和内置工具"""
    type: Optional[str] = None  # 内置工具类型，如 "web_search_20250305"
    name: Optional[str] = None  # 工具名称（自定义工具必需，内置工具可选）
    description: Optional[str] = None  # 工具描述
    input_schema: Optional[Dict[str, Any]] = None  # JSON Schema（自定义工具必需，内置工具无此字段）
    max_uses: Optional[int] = None  # 内置工具参数：最大使用次数


class MessagesRequest(BaseModel):
    """
    Anthropic Messages API 请求
    
    参考: https://docs.anthropic.com/claude/reference/messages_post
    """
    model: Optional[str] = None  # 模型名称（可选，由路由配置决定）
    messages: List[AnthropicMessage]  # 消息列表
    system: Optional[Union[str, List[Dict[str, Any]]]] = None  # 系统提示（Anthropic 独立字段）
    max_tokens: int = Field(default=4096, ge=1)  # 最大输出 token 数（Anthropic 必需）
    temperature: Optional[float] = Field(default=None, ge=0, le=1)
    top_p: Optional[float] = Field(default=None, ge=0, le=1)
    top_k: Optional[int] = Field(default=None, ge=0)
    stream: Optional[bool] = False
    stop_sequences: Optional[List[str]] = None  # 停止序列
    tools: Optional[List[ToolDefinition]] = None  # 工具定义
    tool_choice: Optional[Dict[str, Any]] = None  # 工具选择策略
    metadata: Optional[Dict[str, Any]] = None  # 元数据


# ============ 响应相关 Schema ============

class TextBlock(BaseModel):
    """文本响应块"""
    type: str = "text"
    text: str


class ToolUseBlock(BaseModel):
    """工具使用响应块"""
    type: str = "tool_use"
    id: str
    name: str
    input: Dict[str, Any]


class MessagesUsage(BaseModel):
    """Anthropic 用量统计"""
    input_tokens: int
    output_tokens: int


class MessagesResponse(BaseModel):
    """
    Anthropic Messages API 响应
    """
    id: str
    type: str = "message"
    role: str = "assistant"
    content: List[Union[TextBlock, ToolUseBlock]]
    model: str
    stop_reason: Optional[str] = None  # end_turn, max_tokens, stop_sequence, tool_use
    stop_sequence: Optional[str] = None
    usage: MessagesUsage


# ============ 流式响应相关 Schema ============

class MessageStartEvent(BaseModel):
    """message_start 事件"""
    type: str = "message_start"
    message: Dict[str, Any]


class ContentBlockStartEvent(BaseModel):
    """content_block_start 事件"""
    type: str = "content_block_start"
    index: int
    content_block: Dict[str, Any]


class ContentBlockDeltaEvent(BaseModel):
    """content_block_delta 事件"""
    type: str = "content_block_delta"
    index: int
    delta: Dict[str, Any]


class ContentBlockStopEvent(BaseModel):
    """content_block_stop 事件"""
    type: str = "content_block_stop"
    index: int


class MessageDeltaEvent(BaseModel):
    """message_delta 事件"""
    type: str = "message_delta"
    delta: Dict[str, Any]
    usage: Optional[Dict[str, Any]] = None


class MessageStopEvent(BaseModel):
    """message_stop 事件"""
    type: str = "message_stop"
