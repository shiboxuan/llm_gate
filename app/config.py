"""
配置管理模块

使用 pydantic-settings 通过环境变量加载配置，前缀 LLM_GATE_。
本地开发可使用项目根目录下的 .env 文件。
"""
from datetime import datetime
from functools import lru_cache
from zoneinfo import ZoneInfo

from pydantic_settings import BaseSettings, SettingsConfigDict


# ════════════════════════════════════════════════════════════════════════════════════════════════════════════════════
# 时区配置
# ════════════════════════════════════════════════════════════════════════════════════════════════════════════════════
TIMEZONE = ZoneInfo("Asia/Shanghai")  # UTC+8 时区，所有发送给数据库的时间都带时区


def get_current_time() -> datetime:
    """获取当前时间（带时区，UTC+8）

    所有需要当前时间的地方都应使用此函数，确保时间带时区信息。

    Returns:
        datetime: 带时区的当前时间
    """
    current_time = datetime.now(TIMEZONE)
    return current_time


class Settings(BaseSettings):
    """应用配置类

    环境变量命名规则：LLM_GATE_ 前缀，例如 LLM_GATE_DATABASE_URL。
    本地开发可写入 .env 文件。
    """

    model_config = SettingsConfigDict(env_prefix="LLM_GATE_", env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # 应用基础配置
    app_name: str = "llm-gate"
    app_env: str = "production"  # development | production
    debug: bool = False

    # Graylog 配置（可选，默认关闭）
    graylog_enabled: bool = False
    graylog_host: str = "localhost"
    graylog_port: int = 12201
    graylog_protocol: str = "tcp"  # tcp | udp | http
    graylog_level: str = "INFO"
    graylog_business: str = "llm_gate"

    # 数据库配置（PostgreSQL，SQLAlchemy 异步直连）
    database_url: str = "postgresql+asyncpg://llm_gate:llm_gate@localhost:5432/llm_gate"

    # Redis 配置
    redis_url: str = "redis://localhost:6379/0"
    redis_cache_ttl: int = 36000  # 10 小时

    # JWT 配置
    jwt_secret_key: str = ""
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 720  # 12小时

    # AES 加密密钥（用于 Provider Key 加密，必须配置）
    aes_secret_key: str = ""

    # 预置管理员配置（首次启动时自动创建该账户）
    admin_username: str = "gate_admin"
    admin_password: str = "change-this-password"

    # Anthropic 代理认证标识：当 base_url 包含此处任一字符串时，使用 Bearer 认证
    # （默认空，即所有 Anthropic 端点统一用官方 x-api-key 认证；自建 Bearer 代理时可配置）
    anthropic_bearer_auth_markers: list[str] = []

    # HTTP 代理超时配置（秒）
    proxy_timeout_connect: float = 10.0       # 连接超时
    proxy_timeout_write: float = 30.0         # 写入超时
    proxy_timeout_pool: float = 10.0          # 连接池超时
    proxy_timeout_read_stream: float = 600.0      # 流式读取超时（10分钟）
    proxy_timeout_read_non_stream: float = 1800.0  # 非流式读取超时（30分钟）


@lru_cache()
def get_settings() -> Settings:
    """获取配置单例（lru_cache 确保只加载一次）"""
    return Settings()
