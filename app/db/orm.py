"""
SQLAlchemy ORM 模型

定义数据库表结构，用于 SQLAlchemy 直连 PostgreSQL。
应用启动时由 db_init_service 通过 metadata.create_all 自动建表（IF NOT EXISTS）。
"""
from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """ORM 基类"""
    pass


class UserORM(Base):
    """用户表 - 注册登录用户（用户名 + 密码 + 管理员角色）"""
    __tablename__ = "users"

    id = Column(String, primary_key=True)
    username = Column(String, unique=True, nullable=False, index=True)
    password_hash = Column(Text, nullable=False)
    email = Column(String, nullable=True)
    is_admin = Column(Boolean, nullable=False, default=False)
    status = Column(SmallInteger, nullable=False, default=1)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class ToolORM(Base):
    """工具表 - 客户端身份标识，拥有 Tool Token 与路由配置"""
    __tablename__ = "tools"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=False, default="")
    token_hash = Column(Text, unique=True, nullable=False)
    api_type = Column(String, nullable=False, default="openai_chat")
    active_route_name = Column(String, nullable=True)
    routes = Column(JSONB, nullable=False, default=dict)
    status = Column(SmallInteger, nullable=False, default=1)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("user_id", "name", name="uq_tools_user_id_name"),
        Index("idx_tools_user_id", "user_id"),
        Index("idx_tools_token_hash", "token_hash"),
    )


class ProviderKeyORM(Base):
    """供应商密钥表 - AES-256-GCM 加密存储"""
    __tablename__ = "provider_keys"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name = Column(String, nullable=False)
    api_key_encrypted = Column(Text, nullable=False)
    status = Column(SmallInteger, nullable=False, default=1)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("user_id", "name", name="uq_provider_keys_user_id_name"),
        Index("idx_provider_keys_user_id", "user_id"),
    )


class UserUsageSummaryORM(Base):
    """用户用量汇总表 - 累计总量，避免全表扫描"""
    __tablename__ = "user_usage_summary"

    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    total_tokens = Column(BigInteger, nullable=False, default=0)
    success_requests = Column(BigInteger, nullable=False, default=0)
    error_requests = Column(BigInteger, nullable=False, default=0)
    updated_at = Column(DateTime(timezone=True), nullable=True, onupdate=func.now())


class UsageRecordORM(Base):
    """用量明细记录表（单表，按 created_at 索引查询）"""
    __tablename__ = "usage_records"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    tool_id = Column(BigInteger, nullable=False)
    route_name = Column(String, nullable=False)
    provider_key_name = Column(String, nullable=False)
    model = Column(String, nullable=False)
    base_url = Column(Text, nullable=False)
    prompt_tokens = Column(BigInteger, nullable=False, default=0)
    completion_tokens = Column(BigInteger, nullable=False, default=0)
    total_tokens = Column(BigInteger, nullable=False, default=0)
    cache_creation_input_tokens = Column(BigInteger, nullable=False, default=0)
    cache_read_input_tokens = Column(BigInteger, nullable=False, default=0)
    cached_tokens = Column(BigInteger, nullable=False, default=0)
    request_id = Column(String, nullable=True)
    api_type = Column(String, nullable=True)
    status = Column(String, nullable=False, default="success")
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        Index("idx_usage_records_user_id", "user_id"),
        Index("idx_usage_records_user_created", "user_id", "created_at"),
        Index("idx_usage_records_tool_id", "tool_id"),
    )
