"""
Chat Schema - Chat Completion Pydantic Schemas
兼容 OpenAI API 格式
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any, Union
from datetime import datetime


class Message(BaseModel):
    """消息结构"""
    role: str                        # system, user, assistant
    content: Optional[Union[str, List[Dict[str, Any]]]] = None  # 文本或多模态内容，assistant消息在有tool_calls时可为None
    name: Optional[str] = None       # 可选的消息发送者名称
    tool_calls: Optional[List[Dict[str, Any]]] = None  # assistant消息的工具调用
    tool_call_id: Optional[str] = None  # tool消息的工具调用ID


class FunctionCall(BaseModel):
    """函数调用结构"""
    name: str
    arguments: str


class ToolCall(BaseModel):
    """工具调用结构"""
    id: str
    type: str = "function"
    function: FunctionCall


class StreamOptions(BaseModel):
    """流式响应选项"""
    include_usage: Optional[bool] = True  # 是否在流式响应中包含 usage 信息


class ChatCompletionRequest(BaseModel):
    """聊天请求（兼容OpenAI格式）"""
    model: Optional[str] = None      # 模型名称（可选，由路由配置决定）
    messages: List[Message]          # 消息列表
    temperature: Optional[float] = Field(default=None, ge=0, le=2)
    top_p: Optional[float] = Field(default=None, ge=0, le=1)
    n: Optional[int] = Field(default=1, ge=1)
    stream: Optional[bool] = False
    stream_options: Optional[StreamOptions] = None  # 流式响应选项
    stop: Optional[Union[str, List[str]]] = None
    max_tokens: Optional[int] = None
    presence_penalty: Optional[float] = Field(default=None, ge=-2, le=2)
    frequency_penalty: Optional[float] = Field(default=None, ge=-2, le=2)
    logit_bias: Optional[Dict[str, float]] = None
    user: Optional[str] = None
    # 函数调用相关
    functions: Optional[List[Dict[str, Any]]] = None
    function_call: Optional[Union[str, Dict[str, str]]] = None
    # 工具调用相关
    tools: Optional[List[Dict[str, Any]]] = None
    tool_choice: Optional[Union[str, Dict[str, Any]]] = None
    # 其他参数
    response_format: Optional[Dict[str, str]] = None
    seed: Optional[int] = None


class Usage(BaseModel):
    """Token 用量"""
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class ChoiceMessage(BaseModel):
    """响应消息"""
    role: str = "assistant"
    content: Optional[str] = None
    function_call: Optional[FunctionCall] = None
    tool_calls: Optional[List[ToolCall]] = None


class Choice(BaseModel):
    """响应选项"""
    index: int
    message: ChoiceMessage
    finish_reason: Optional[str] = None


class ChatCompletionResponse(BaseModel):
    """聊天响应"""
    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: List[Choice]
    usage: Optional[Usage] = None
    system_fingerprint: Optional[str] = None


# Streaming 相关
class DeltaMessage(BaseModel):
    """流式响应增量消息"""
    role: Optional[str] = None
    content: Optional[str] = None
    function_call: Optional[Dict[str, str]] = None
    tool_calls: Optional[List[Dict[str, Any]]] = None


class StreamChoice(BaseModel):
    """流式响应选项"""
    index: int
    delta: DeltaMessage
    finish_reason: Optional[str] = None


class ChatCompletionStreamResponse(BaseModel):
    """流式聊天响应"""
    id: str
    object: str = "chat.completion.chunk"
    created: int
    model: str
    choices: List[StreamChoice]
    system_fingerprint: Optional[str] = None
