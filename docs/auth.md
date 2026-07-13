# 认证机制

本文档说明 LLM Gate 的认证体系：控制面的用户注册登录，以及数据面的 Tool Token 认证。

## 一、控制面：用户注册登录

### 1.1 认证模型

- **身份标识**：用户名（`username`，唯一）
- **凭证**：密码（bcrypt 哈希存储，明文不落库）
- **角色**：`is_admin`（布尔值，管理员 / 普通用户）
- **状态**：`status`（1=正常，0=禁用）

### 1.2 注册

**端点**：`POST /api/auth/register`

**请求体**：
```json
{
  "username": "alice",
  "password": "at-least-8-chars",
  "email": "alice@example.com"
}
```

- `username`：3-32 位，仅字母数字下划线连字符，唯一
- `password`：至少 8 位
- `email`：可选

**行为**：
1. 校验用户名唯一（冲突返回 409）
2. 若提供 email，校验唯一
3. bcrypt 哈希密码
4. 创建用户（`is_admin=false`，普通用户）
5. 签发 JWT，返回 `{access_token, user}`（注册后无需再次登录）

> 注册接口始终创建**普通用户**。管理员账户通过预置机制创建（见 1.5）。

### 1.3 登录

**端点**：`POST /api/auth/login`

**请求体**：
```json
{
  "username": "alice",
  "password": "at-least-8-chars"
}
```

**行为**：
1. 按 `username` 查询用户
2. `bcrypt.verify` 校验密码（用户名或密码错误统一返回 401，不泄露用户是否存在）
3. 校验 `status == 1`（禁用账户返回 403）
4. 签发 JWT，返回 `{access_token, user}`

### 1.4 JWT

- **算法**：HS256
- **密钥**：`LLM_GATE_JWT_SECRET_KEY`（必须配置）
- **有效期**：默认 720 分钟（12 小时），由 `LLM_GATE_JWT_ACCESS_TOKEN_EXPIRE_MINUTES` 配置
- **载荷**：
  ```json
  {
    "sub": "user_xxxxxxxxxxxx",   // user_id
    "username": "alice",
    "is_admin": false,
    "exp": 1234567890,
    "iat": 1234567890
  }
  ```

**使用方式**：后续请求在 `Authorization` 头携带 `Bearer <access_token>`。

**获取当前用户**：`GET /api/auth/me`（需 JWT），返回当前用户信息。

### 1.5 预置管理员

为便于部署后立即使用，应用首次启动时自动预置管理员账户：

- **用户名**：`LLM_GATE_ADMIN_USERNAME`（默认 `gate_admin`）
- **密码**：`LLM_GATE_ADMIN_PASSWORD`（默认 `qweasdzxc123321`）
- **角色**：`is_admin=true`

预置逻辑在 `db_init_service._ensure_admin_user`：若该用户名不存在则创建，已存在则跳过。

> ⚠️ **生产环境务必通过环境变量修改默认密码**，并在首次登录后及时更换。

### 1.6 密码哈希

使用 `passlib` 的 bcrypt 方案（`app/core/security.py`）：

- `hash_password(password)` -> bcrypt 哈希
- `verify_password(password, hash)` -> 校验

bcrypt 自带盐值与慢哈希，抗暴力破解。

### 1.7 角色与数据隔离

- 所有控制面端点通过 `Depends(get_current_user)` 注入当前用户。
- 资源（Tool / ProviderKey / 用量记录）按 `user_id` 隔离：用户只能操作自己的资源。
- `is_admin` 字段当前作为角色标记保留，未启用额外管理员特权页面。管理员 `gate_admin` 登录后管理其名下的 gate 配置（即"部署账户的 gate 配置"）。

## 二、数据面：Tool Token 认证

数据面 `/v1/*` 端点不使用 JWT，使用 **Tool Token**：

### 2.1 认证流程

1. 客户端在 `Authorization` 头携带 `Bearer <tool_token>`
2. 网关计算 `SHA-256(tool_token)` 得到 `token_hash`
3. 查 Redis 缓存（`route_config:{token_hash}`）
4. 缓存未命中：查 `tools` 表（按 `token_hash`），解密 provider key，缓存结果
5. 使用解密后的真实 API Key 转发请求到 LLM 提供商

### 2.2 Tool Token 生命周期

- **创建**：管理员/用户在控制面创建 Tool 时，网关生成 `sk-{random}` 格式的 Tool Token，**仅在创建时返回一次**（存储的是 SHA-256 哈希）。
- **重置**：`POST /api/tools/{id}/regenerate-key` 生成新 Token，旧 Token 立即失效（缓存清除）。
- **保管**：客户端（如 Cline、Cursor）在配置中填入 Tool Token，用于访问 `/v1/*`。

## 三、认证链路图

```
┌─────────────┐
│  浏览器/前端  │  注册/登录 (username + password)
└──────┬──────┘
       │ POST /api/auth/login
       ▼
┌─────────────┐   JWT (sub=user_id, username, is_admin)
│  控制面 API  │ ◄──────────────────────────────────────┐
│  /api/*     │   Authorization: Bearer <jwt>           │
└─────────────┘                                          │
       │ 创建 Tool，获得 Tool Token                       │
       ▼                                                  │
┌─────────────┐                                          │
│   客户端     │  Cline / Cursor 等                       │
│ (AI 工具)   │  Authorization: Bearer <tool_token>      │
└──────┬──────┘                                          │
       │ POST /v1/chat/completions                        │
       ▼                                                  │
┌─────────────┐   校验 tool_token -> 解密 provider key    │
│  数据面 API  │ ───────────────────────────────────────┘
│  /v1/*      │   转发到 LLM 提供商
└─────────────┘
```
