"""
Embedding Schema - Embeddings API Pydantic Schemas
兼容 OpenAI Embeddings API 格式

参考: https://platform.openai.com/docs/api-reference/embeddings
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Union, Literal


class EmbeddingRequest(BaseModel):
    """
    Embeddings API 请求模型（OpenAI 兼容）
    """
    input: Union[str, List[List[int]], List[int], List[str]] = Field(
        ...,
        description="Input text to embed, encoded as a string, array of strings, array of integers (token IDs), or array of arrays of integers."
    )

    model: Optional[str] = Field(
        None,
        description="Model to use for embedding. If not provided, uses route config model."
    )

    encoding_format: Optional[Literal["float", "base64"]] = Field(
        None,
        description="The format to return the embeddings in. Can be 'float' or 'base64'."
    )

    dimensions: Optional[int] = Field(
        None,
        ge=1,
        description="The number of dimensions the resulting output embeddings should have. "
                    "Only supported in text-embedding-3 and later models."
    )

    user: Optional[str] = Field(
        None,
        description="A unique identifier representing your end-user"
    )


class EmbeddingObject(BaseModel):
    """单个 embedding 对象"""
    object: str = "embedding"
    embedding: List[float]
    index: int


class EmbeddingUsage(BaseModel):
    """用量统计"""
    prompt_tokens: int
    total_tokens: int


class EmbeddingResponse(BaseModel):
    """Embeddings API 响应模型"""
    object: str = "list"
    data: List[EmbeddingObject]
    model: str
    usage: EmbeddingUsage
