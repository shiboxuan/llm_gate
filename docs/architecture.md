# 架构说明

本文档说明 LLM Gate 的整体架构、技术选型与关键设计。

## 一、架构概述

LLM Gate 是一个 LLM API 网关，采用**控制面 + 数据面分离**架构：

- **控制面**（`/api/*`）：管理 API，供管理员/用户注册登录、配置 Tool/Route/ProviderKey、查看用量统计。认证方式为 JWT（用户名密码）。
- **数据面**（`/v1/*`）：代理 API，供 AI 客户端（Cline、Cursor 等）以 Tool Token 认证，转发请求到真实 LLM 提供商。

```
┌─────────────────────────────────────────────────────────┐
│                      LLM Gate                           │
│                                                         │
│  ┌──────────────┐         ┌──────────────────────────┐ │
│  │  控制面 /api  │         │      数据面 /v1          │ │
│  │  注册/登录    │         │  /chat/completions       │ │
│  │  Tool CRUD   │         │  /messages               │ │
│  │  密钥管理     │         │  /responses              │ │
│  │  用量统计     │         │  /embeddings             │ │
│  └──────┬───────┘         └──────────┬───────────────┘ │
│         │ JWT                         │ Tool Token      │
│         ▼                            ▼                  │
│  ┌──────────────────────────────────────────────────┐  │
│  │              Service 业务逻辑层                  │  │
│  │  UserService / ToolService / ProxyService ...    │  │
│  └──────────┬──────────────────────┬────────────────┘  │
│             ▼                      ▼                   │
│  ┌──────────────────┐    ┌──────────────────┐         │
│  │  PostgreSQL      │    │  Redis (缓存)    │         │
│  │  (SQLAlchemy)    │    │  路由配置/用量    │         │
│  └──────────────────┘    └──────────────────┘         │
└─────────────────────────────────────────────────────────┘
```

## 二、技术栈

### 后端
- **Web 框架**：FastAPI + Uvicorn
- **数据库 ORM**：SQLAlchemy 2.0（async）+ asyncpg，直连 PostgreSQL
- **缓存**：Redis（redis-py async）
- **认证**：python-jose（JWT）+ passlib（bcrypt 密码哈希）
- **加密**：cryptography（AES-256-GCM，Provider Key 加密）
- **HTTP 客户端**：httpx（异步，转发 LLM 请求）
- **配置**：pydantic-settings

### 前端
- **框架**：React 18 + TypeScript
- **构建**：Webpack 5
- **UI**：Ant Design 5 + @ant-design/pro-components
- **状态**：zustand
- **路由**：react-router 7

### 部署
- **单镜像**：多阶段 Docker 构建，前端产物由 FastAPI 静态托管

## 三、目录结构

```
llm_gate/
├── app/                            # 后端
│   ├── api/
│   │   ├── control_plane/          # 控制面 API (/api/*)
│   │   │   ├── auth.py             # 注册/登录/me
│   │   │   ├── tools.py            # Tool CRUD
│   │   │   ├── provider_keys.py    # 密钥管理
│   │   │   ├── usage.py            # 用量统计
│   │   │   └── router.py
│   │   └── data_plane/             # 数据面 API (/v1/*)
│   │       ├── chat.py             # OpenAI Chat
│   │       ├── messages.py         # Anthropic Messages
│   │       ├── responses.py        # OpenAI Responses
│   │       └── embeddings.py
│   ├── services/                   # 业务逻辑层
│   │   ├── user_service.py
│   │   ├── tool_service.py
│   │   ├── route_service.py
│   │   ├── provider_key_service.py
│   │   ├── proxy_service.py        # LLM 请求转发核心
│   │   ├── usage_service.py
│   │   ├── cache_service.py        # Redis 路由缓存
│   │   ├── connection_test_service.py
│   │   └── db_init_service.py      # 建表 + 预置管理员
│   ├── db/
│   │   ├── orm.py                  # SQLAlchemy ORM 模型
│   │   ├── session.py              # async engine + session
│   │   └── redis.py                # Redis 连接管理
│   ├── core/
│   │   ├── security.py             # JWT / AES / Tool Token / bcrypt
│   │   ├── dependencies.py         # FastAPI 依赖注入
│   │   ├── exceptions.py           # 异常体系
│   │   └── error_codes.py
│   ├── models/                     # Pydantic 数据模型
│   ├── schemas/                    # API 请求/响应 Schema
│   ├── middleware/                 # 日志/请求ID/安全头
│   ├── logger_mgr/                 # 日志（含可选 Graylog）
│   ├── config.py                   # 配置
│   └── main.py                     # 应用入口
├── frontend/                       # 前端独立工程
├── docs/                           # 文档
├── tests/                          # 测试
├── Dockerfile                      # 单镜像构建
├── requirements.txt
├── run.py                          # 启动脚本
└── .env.example
```

## 四、数据流

### 4.1 控制面请求

1. 前端登录，获得 JWT
2. 携带 JWT 调用 `/api/*` 管理资源
3. `get_current_user` 依赖解析 JWT，注入当前用户
4. Service 层通过 `AsyncSession` 操作 PostgreSQL（按 `user_id` 隔离）
5. 返回结果

### 4.2 数据面代理请求

1. 客户端携带 Tool Token 请求 `/v1/chat/completions`
2. `ProxyService.resolve_route_config`：
   - 计算 `SHA-256(tool_token)` -> `token_hash`
   - 查 Redis 缓存 `route_config:{token_hash}`
   - 未命中：查 `tools` 表，解密 provider key，构建配置，写缓存
3. 用真实 API Key 转发请求到 LLM 提供商（支持流式）
4. 返回响应给客户端
5. 后台记录用量（`usage_records` + `user_usage_summary`）

## 五、关键设计决策

### 5.1 数据访问：SQLAlchemy 直连

后端通过 SQLAlchemy 2.0 async 直连 PostgreSQL（`app/db/orm.py` + `app/db/session.py`）。Service 层通过 `AsyncSession`（FastAPI 依赖注入）操作数据库。

- 写操作：`record_usage` 在 background task 中调用，内部自建独立 session（请求 session 已关闭）
- 读操作：使用请求级 session

### 5.2 单镜像部署

前端构建产物在 Docker 多阶段构建时拷贝到后端镜像的 `static/` 目录，由 FastAPI `StaticFiles` 托管。非 API 路径 fallback 到 `index.html`（SPA 路由）。

### 5.3 Provider Key 加密

Provider Key 使用 AES-256-GCM 加密存储（`app/core/security.py`），密钥为 `LLM_GATE_AES_SECRET_KEY`。仅在转发请求时解密，明文不落库、不进日志（日志脱敏 `sanitize_for_log`）。

### 5.4 路由配置缓存

数据面代理时，路由配置按 `token_hash` 缓存到 Redis（TTL 10 小时）。Tool Token 重置或 Provider Key 变更时主动失效缓存。

## 六、相关文档

- [认证机制](auth.md)
- [基础设施清单](infrastructure.md)
- [部署指南](deployment.md)
- [脱敏报告](sanitization-report.md)
