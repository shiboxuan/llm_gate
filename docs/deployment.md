# 部署指南

本文档说明如何部署 LLM Gate。推荐使用**单镜像部署**（前后端合一）。

## 一、前置条件

部署前请先准备好基础设施（详见 [infrastructure.md](infrastructure.md)）：

- PostgreSQL 14+（已创建数据库 `llm_gate` 与用户）
- Redis 6+
- Docker 20+
- Node.js 18+（仅构建镜像时需要）

## 二、配置环境变量

在项目根目录创建 `.env` 文件（参考 `.env.example`）：

```bash
# 数据库（修改为实际地址与密码）
LLM_GATE_DATABASE_URL=postgresql+asyncpg://llm_gate:YOUR_PASSWORD@your-pg-host:5432/llm_gate

# Redis
LLM_GATE_REDIS_URL=redis://your-redis-host:6379/0

# JWT 密钥（必填，32+ 位随机字符串）
LLM_GATE_JWT_SECRET_KEY=your-random-jwt-secret

# AES 加密密钥（必填，32 字节随机字符串）
LLM_GATE_AES_SECRET_KEY=your-random-32-byte-aes-secret

# 预置管理员（首次启动自动创建，建议修改密码）
LLM_GATE_ADMIN_USERNAME=gate_admin
LLM_GATE_ADMIN_PASSWORD=your-strong-admin-password

# 可选：Anthropic Bearer 认证代理标识
# LLM_GATE_ANTHROPIC_BEARER_AUTH_MARKERS=["your-proxy-marker"]
```

> ⚠️ 生产环境务必修改 `JWT_SECRET_KEY`、`AES_SECRET_KEY`、`ADMIN_PASSWORD` 为强随机值。

## 三、单镜像部署（推荐）

### 3.1 构建镜像

```bash
docker build -f Dockerfile -t llm_gate:latest .
```

构建过程：
1. Stage 1（node:18-alpine）：安装前端依赖，`npm run build` 生成前端产物
2. Stage 2（python:3.11-slim）：安装后端依赖，拷贝后端代码 + 前端产物到 `static/`

### 3.2 运行容器

```bash
docker run -d \
  --name llm_gate \
  -p 9981:9981 \
  --env-file .env \
  llm_gate:latest
```

### 3.3 验证

```bash
# 健康检查
curl http://localhost:9981/health
# 期望: {"status":"healthy","app_name":"llm-gate","app_env":"production"}

# 访问前端
# 浏览器打开 http://localhost:9981/

# API 文档
# 浏览器打开 http://localhost:9981/docs
```

### 3.4 首次启动行为

容器首次启动时会：
1. 连接 PostgreSQL 与 Redis（失败则容器退出）
2. 自动建表（`CREATE TABLE IF NOT EXISTS`）
3. 预置管理员账户 `gate_admin`（若不存在）
4. 启动 FastAPI 服务，监听 9981

### 3.5 登录

- 访问 `http://<host>:9981/`
- 使用预置管理员登录：用户名 `gate_admin`，密码为 `LLM_GATE_ADMIN_PASSWORD` 配置的值
- 登录后可创建 Tool、配置路由、管理 Provider Key

## 四、开发模式（前后端分离）

开发时前后端可分别启动：

### 4.1 后端

```bash
# 配置 .env（指向本地 PG/Redis）
python run.py
# 后端启动在 http://localhost:9981
```

### 4.2 前端

```bash
cd frontend
npm install
npm run dev
# 前端 dev server 启动在 http://localhost:9000
```

前端 dev server 会通过环境变量 `LLM_GATE_HOST` 指向后端（开发期跨域，后端已开启 CORS）。

## 五、日志

- 默认输出到 stdout（容器标准输出，可用 `docker logs llm_gate` 查看）
- 可选 Graylog：配置 `LLM_GATE_GRAYLOG_ENABLED=true` 及相关参数
- 日志自动脱敏 API Key（`sanitize_for_log`）

## 六、常见问题

### 6.1 容器启动失败：数据库连接错误

检查 `LLM_GATE_DATABASE_URL` 是否正确，PostgreSQL 是否可达，用户是否有 `llm_gate` 数据库权限。

### 6.2 容器启动失败：Redis 连接错误

检查 `LLM_GATE_REDIS_URL` 是否正确，Redis 是否可达。

### 6.3 前端页面空白

确认镜像构建时前端产物已生成（`static/index.html` 存在）。可进入容器检查：`docker exec llm_gate ls /app/static`。

### 6.4 忘记管理员密码

修改 `LLM_GATE_ADMIN_PASSWORD` 环境变量后重启容器**不会**重置已存在的管理员密码（预置仅在用户不存在时创建）。如需重置，可直接操作数据库删除 `users` 表中 `gate_admin` 记录后重启，或通过 SQL 更新 `password_hash`（bcrypt 哈希）。
