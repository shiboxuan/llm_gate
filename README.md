# LLM Gate

> 🚀 一个可扩展的 LLM Gateway / 控制面 + 数据面分离架构
> 支持多工具、多路由、动态模型切换
> 持久化使用 PostgreSQL（SQLAlchemy 直连），缓存使用 Redis

---

## 一、项目背景

在使用 LLM 时，经常面临以下问题：

| 痛点 | 描述 |
|------|------|
| 🔄 模型切换繁琐 | 不同工具（Cline、Cursor、自研 App）需要频繁手动切换模型配置 |
| 🔐 密钥管理混乱 | API Key 分散在各个客户端，安全性低、审计困难 |
| ⚙️ 配置维护成本高 | 切换模型/Provider 需要修改每个客户端配置 |
| 📊 缺乏统一管控 | 无法统一限流、监控、统计 |

**LLM Gate 通过统一网关 + 动态路由的方式，让客户端只需持有一个 Tool Token，即可透明访问任意后端 LLM Provider。**

---

## 二、系统架构

```
┌─────────────────────────────────────────────────────────────────┐
│                         Clients                                 │
│     ┌─────────┐     ┌─────────┐     ┌─────────────┐            │
│     │  Cline  │     │ Cursor  │     │ Internal App│            │
│     └────┬────┘     └────┬────┘     └──────┬──────┘            │
│          │               │                  │                   │
│          └───────────────┼──────────────────┘                   │
│                          │ Tool Token                           │
│                          ▼                                      │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │                     LLM Gate                              │  │
│  │  ┌─────────────┐    ┌─────────────┐    ┌──────────────┐  │  │
│  │  │   Auth &    │───▶│   Router    │───▶│   Proxy      │  │  │
│  │  │  Rate Limit │    │   Engine    │    │   Forward    │  │  │
│  │  └─────────────┘    └─────────────┘    └──────────────┘  │  │
│  │         │                  │                   │          │  │
│  │         ▼                  ▼                   ▼          │  │
│  │  ┌─────────────────────────────────────────────────────┐ │  │
│  │  │                    Redis Cache                      │ │  │
│  │  │       route_config:{token_hash} -> RouteConfig      │ │  │
│  │  └─────────────────────────────────────────────────────┘ │  │
│  │                          │ Cache Miss                     │  │
│  │                          ▼                                │  │
│  │  ┌─────────────────────────────────────────────────────┐ │  │
│  │  │                   PostgreSQL                        │ │  │
│  │  │     users │ tools │ provider_keys │ usage_records   │ │  │
│  │  └─────────────────────────────────────────────────────┘ │  │
│  └──────────────────────────────────────────────────────────┘  │
│                          │                                      │
│                          ▼                                      │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │                   LLM Providers                           │  │
│  │   ┌─────────┐   ┌───────────┐   ┌─────────┐   ┌───────┐  │  │
│  │   │ OpenAI  │   │ Anthropic │   │  Azure  │   │ Custom│  │  │
│  │   └─────────┘   └───────────┘   └─────────┘   └───────┘  │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 三、核心概念

系统包含四个核心实体：

### 1️⃣ User（用户）

注册用户，所有资源的归属主体。通过用户名密码注册登录。

| 字段 | 说明 |
|------|------|
| id | 用户唯一标识 |
| username | 用户名（唯一） |
| password_hash | 密码哈希（bcrypt） |
| email | 邮箱（可选） |
| is_admin | 是否管理员 |
| status | 状态（1=启用，0=禁用） |

首次启动自动预置管理员 `gate_admin`。

### 2️⃣ Provider Key（供应商密钥）

用户绑定的真实 LLM Provider API Key。

| 支持的 Provider | 示例 |
|----------------|------|
| OpenAI | `sk-proj-xxxx` |
| Anthropic | `sk-ant-xxxx` |
| Azure OpenAI | `xxxxx` |
| 自定义 Provider | 任意兼容 OpenAI API 格式的服务 |

**特点：**
- 密钥使用 AES-256-GCM 加密存储
- 支持按名称引用，避免密钥硬编码
- 一个用户可以绑定多个 Provider Key

### 3️⃣ Tool（工具）

Tool 是"调用身份"，代表一个客户端/应用。

| 示例 Tool | 说明 |
|-----------|------|
| Cline | VS Code AI 编程插件 |
| Cursor | AI 代码编辑器 |
| 内部系统 | 自研应用 |

**每个 Tool：**
- ✅ 拥有唯一 Tool Token（`sk-xxx`，仅创建时返回一次，存储 SHA-256 哈希）
- ✅ 关联多个 Route 配置
- ✅ 任意时刻仅激活一个 Route
- ✅ 客户端只需使用 Tool Token 调用，无需关心后端 Provider

### 4️⃣ Route（路由）

Route 是一组实际的 LLM 调用配置。

| 字段 | 说明 | 示例 |
|------|------|------|
| base_url | API 端点 | `https://api.openai.com/v1` |
| model | 模型名称 | `gpt-4o`、`claude-3-5-sonnet` |
| provider_key_name | 引用的密钥名称 | `my-openai-key` |
| order | 排序 | 0 |

**一个 Tool 可配置多个 Route，通过 `active_route_name` 切换激活的路由。**

---

## 四、快速开始

### 4.1 准备基础设施

详见 [docs/infrastructure.md](docs/infrastructure.md)：PostgreSQL 14+、Redis 6+（无需额外 PG 扩展）。

### 4.2 配置环境变量

```bash
cp .env.example .env
# 编辑 .env，填入数据库、Redis、JWT/AES 密钥
```

### 4.3 单镜像部署（前后端合一）

```bash
docker build -f Dockerfile -t llm_gate:latest .
docker run -d -p 9981:9981 --env-file .env llm_gate:latest
```

启动后访问 `http://localhost:9981/`，用预置管理员 `gate_admin` 登录。

### 4.4 开发模式

```bash
# 后端
python run.py

# 前端（另一个终端）
cd frontend && npm install && npm run dev
```

---

## 五、API 设计

### 数据面（Data Plane）- 代理请求

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/v1/chat/completions` | OpenAI Chat API |
| POST | `/v1/messages` | Anthropic Messages API |
| POST | `/v1/responses` | OpenAI Responses API |
| POST | `/v1/embeddings` | OpenAI Embeddings API |

数据面使用 Tool Token 认证：`Authorization: Bearer {tool_token}`

### 控制面（Control Plane）- 管理接口

#### 认证
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/auth/register` | 注册（用户名+密码） |
| POST | `/api/auth/login` | 登录 |
| GET | `/api/auth/me` | 获取当前用户 |

#### 工具管理
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/tools` | 创建 Tool |
| GET | `/api/tools` | 获取用户的所有 Tools |
| GET | `/api/tools/{id}` | 获取 Tool 详情 |
| PUT | `/api/tools/{id}` | 更新 Tool |
| DELETE | `/api/tools/{id}` | 删除 Tool |
| POST | `/api/tools/{id}/routes` | 添加 Route |
| PUT | `/api/tools/{id}/routes/{name}` | 更新 Route |
| DELETE | `/api/tools/{id}/routes/{name}` | 删除 Route |
| PUT | `/api/tools/{id}/activate/{route_name}` | 切换激活的 Route |
| POST | `/api/tools/{id}/regenerate-key` | 重新生成 Tool Token |

#### Provider Key 管理
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/provider-keys` | 创建 Provider Key |
| GET | `/api/provider-keys` | 获取用户的所有 Keys |
| DELETE | `/api/provider-keys/{id}` | 删除 Provider Key |

#### 用量统计
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/usage/overview` | 用量总览 |
| GET | `/api/usage/records` | 用量明细记录 |

控制面使用 JWT 认证：`Authorization: Bearer {jwt}`

---

## 六、请求流程

### Chat Completions 请求时序

#### ✅ 缓存命中
```
┌────────┐       ┌──────────┐       ┌───────┐       ┌──────────────┐
│ Client │       │ LLM Gate │       │ Redis │       │ LLM Provider │
└───┬────┘       └────┬─────┘       └───┬───┘       └──────┬───────┘
    │  POST /v1/chat/completions        │                  │
    │  Authorization: Bearer sk-xxx     │                  │
    │────────────────▶│                 │                  │
    │                 │  GET route_config:{hash}           │
    │                 │────────────────▶│                  │
    │                 │  RouteConfig ✅  │                  │
    │                 │◀────────────────│                  │
    │                 │  Forward (real API Key)             │
    │                 │───────────────────────────────────▶│
    │                 │  LLM Response (stream)             │
    │                 │◀───────────────────────────────────│
    │  Response       │                 │                  │
    │◀────────────────│                 │                  │
```

#### ❌ 缓存未命中
```
┌────────┐     ┌──────────┐     ┌───────┐     ┌────────────┐     ┌──────────────┐
│ Client │     │ LLM Gate │     │ Redis │     │ PostgreSQL │     │ LLM Provider │
└───┬────┘     └────┬─────┘     └───┬───┘     └─────┬──────┘     └──────┬───────┘
    │  Request      │               │               │                   │
    │──────────────▶│  GET (miss)   │               │                   │
    │               │──────────────▶│               │                   │
    │               │  NULL ❌       │               │                   │
    │               │◀──────────────│               │                   │
    │               │  Query tools by token_hash    │                   │
    │               │──────────────────────────────▶│                   │
    │               │  Tool + Routes                │                   │
    │               │◀──────────────────────────────│                   │
    │               │  Query provider_keys, decrypt │                   │
    │               │──────────────────────────────▶│                   │
    │               │  Encrypted API Key            │                   │
    │               │◀──────────────────────────────│                   │
    │               │  SET (cache)  │               │                   │
    │               │──────────────▶│               │                   │
    │               │  Forward Request              │                   │
    │               │──────────────────────────────────────────────────▶│
    │  Response     │               │               │                   │
    │◀──────────────│               │               │                   │
```

---

## 七、文档

详细文档见 [docs/](docs/)：

- [架构说明](docs/architecture.md)
- [认证机制](docs/auth.md)
- [基础设施清单](docs/infrastructure.md)
- [部署指南](docs/deployment.md)
- [脱敏报告](docs/sanitization-report.md)

---

## 八、路线图

- [x] 基础代理功能（OpenAI Chat / Anthropic Messages / Responses / Embeddings）
- [x] 多 Route 动态切换
- [x] Redis 缓存层
- [x] Web 管理界面（注册登录 + 工具/密钥/用量管理）
- [x] 用户名密码注册登录（bcrypt + JWT）
- [x] 单镜像部署前后端
- [ ] 管理员特权页面（用户管理 / 全局用量）

---

## 九、技术栈

**后端**：FastAPI + SQLAlchemy 2.0 (async) + asyncpg + Redis + python-jose (JWT) + passlib (bcrypt) + cryptography (AES)

**前端**：React 18 + TypeScript + Webpack 5 + Ant Design 5 + zustand

**部署**：Docker 多阶段构建，单镜像

---

## License

MIT
