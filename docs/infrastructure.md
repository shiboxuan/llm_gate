# 基础设施清单

本文档列出部署 LLM Gate 所需的全部基础设施，按"一次性部署完"的目标组织。请按顺序准备。

## 一、基础设施总览

| 组件 | 版本要求 | 用途 | 是否必需 |
|------|----------|------|----------|
| PostgreSQL | 14+ | 持久化存储（用户、工具、路由、密钥、用量记录） | ✅ 必需 |
| Redis | 6+ | 路由配置缓存、用量统计缓存 | ✅ 必需 |
| Docker | 20+ | 构建/运行单镜像 | ✅ 必需（推荐） |
| Node.js | 18+ | 前端构建（仅构建时需要，运行时不需要） | ✅ 构建必需 |
| Python | 3.11+ | 后端运行时（已包含在镜像内） | 镜像内自带 |

## 二、PostgreSQL（重点）

### 2.1 版本与扩展

- **版本**：PostgreSQL **14 或以上**（推荐 16）。
- **扩展**：**无需安装任何额外扩展**。
  - 本项目使用的所有数据库特性均为 PostgreSQL 内置能力：
    - `JSONB`（存储 `tools.routes` 路由配置）—— 内置类型，无需 `CREATE EXTENSION`
    - 普通字段类型（`TEXT` / `BIGINT` / `SMALLINT` / `BOOLEAN` / `TIMESTAMPTZ`）
    - 索引、外键、`UNIQUE` 约束、`ON DELETE CASCADE`
  - 用量记录采用**单表 + 索引**（`idx_usage_records_user_created`），不使用原生分区，因此**不需要 `pg_partman` 等分区扩展**。
  - 密钥加密（AES-256-GCM）在**应用层**完成，不依赖 `pgcrypto`。

### 2.2 数据库与用户初始化

连接 PostgreSQL 后执行：

```sql
-- 创建数据库
CREATE DATABASE llm_gate WITH ENCODING 'UTF8';

-- 创建用户（请修改密码）
CREATE USER llm_gate WITH PASSWORD 'llm_gate';

-- 授权
GRANT ALL PRIVILEGES ON DATABASE llm_gate TO llm_gate;

-- 连接到 llm_gate 数据库后，授权 schema 权限
\c llm_gate
GRANT ALL ON SCHEMA public TO llm_gate;
```

### 2.3 表结构

**无需手动建表**。应用启动时（`run.py` -> `db_init_service.ensure_database_ready`）会通过 SQLAlchemy `metadata.create_all` 自动创建所有表（`IF NOT EXISTS`），并预置管理员账户 `gate_admin`。

如需手动建表或查看结构，参考以下表：

| 表名 | 说明 | 关键字段 |
|------|------|----------|
| `users` | 注册用户 | `id`(TEXT PK), `username`(UNIQUE), `password_hash`, `email`, `is_admin`, `status` |
| `tools` | 工具（客户端身份） | `id`(BIGSERIAL PK), `user_id`(FK), `name`, `token_hash`(UNIQUE), `api_type`, `active_route_name`, `routes`(JSONB) |
| `provider_keys` | 供应商密钥 | `id`(BIGSERIAL PK), `user_id`(FK), `name`, `api_key_encrypted`, `status` |
| `user_usage_summary` | 用户用量汇总 | `user_id`(PK), `total_tokens`, `success_requests`, `error_requests` |
| `usage_records` | 用量明细记录 | `id`(BIGSERIAL PK), `user_id`, `tool_id`, `route_name`, `total_tokens`, `created_at` |

完整表结构定义见 `app/db/orm.py`。

## 三、Redis

### 3.1 版本

- Redis **6 或以上**。

### 3.2 用途

- **路由配置缓存**：`route_config:{tool_token_hash}`，TTL 10 小时（`LLM_GATE_REDIS_CACHE_TTL`）
- **用量统计缓存**：`usage_overview:{user_id}`，TTL 60 秒

### 3.3 初始化

无需特殊配置，只需一个可用的 Redis 实例。建议设置 `maxmemory-policy allkeys-lru`。

```bash
# docker 快速启动
docker run -d --name llm_gate_redis -p 6379:6379 redis:7
```

## 四、环境变量配置

将以下环境变量配置到 `.env` 文件（参考 `.env.example`）或通过 Docker 环境变量注入：

```bash
# 数据库（必填，修改为实际地址与密码）
LLM_GATE_DATABASE_URL=postgresql+asyncpg://llm_gate:llm_gate@<pg-host>:5432/llm_gate

# Redis（必填）
LLM_GATE_REDIS_URL=redis://<redis-host>:6379/0

# JWT 密钥（必填，建议 32+ 位随机字符串）
LLM_GATE_JWT_SECRET_KEY=<random-secret>

# AES 加密密钥（必填，建议 32 字节随机字符串，用于 Provider Key 加密）
LLM_GATE_AES_SECRET_KEY=<random-32-byte-secret>

# 预置管理员（首次启动自动创建，建议修改默认密码）
LLM_GATE_ADMIN_USERNAME=gate_admin
LLM_GATE_ADMIN_PASSWORD=qweasdzxc123321
```

> ⚠️ **生产环境务必修改** `LLM_GATE_JWT_SECRET_KEY`、`LLM_GATE_AES_SECRET_KEY`、`LLM_GATE_ADMIN_PASSWORD` 为强随机值。

## 五、部署方式：单镜像

LLM Gate 采用**单镜像部署前后端**：前端构建产物在 Docker 构建阶段生成，拷贝到后端镜像，由 FastAPI 静态托管。

### 5.1 构建

```bash
docker build -f Dockerfile -t llm_gate:latest .
```

### 5.2 运行

```bash
docker run -d \
  --name llm_gate \
  -p 9981:9981 \
  --env-file .env \
  llm_gate:latest
```

启动后：
- 前端：`http://<host>:9981/`
- API 文档：`http://<host>:9981/docs`
- 健康检查：`http://<host>:9981/health`

### 5.3 首次启动行为

1. 连接 PostgreSQL 与 Redis（失败则启动失败）
2. 自动建表（`CREATE TABLE IF NOT EXISTS`）
3. 预置管理员账户 `gate_admin`（若不存在则创建）
4. 启动 FastAPI 服务（监听 9981）

## 六、部署 Checklist

一次性部署完，按以下顺序操作：

- [ ] 1. 准备 PostgreSQL 14+ 实例，创建数据库 `llm_gate` 与用户
- [ ] 2. 准备 Redis 6+ 实例
- [ ] 3. 生成强随机的 `JWT_SECRET_KEY` 和 `AES_SECRET_KEY`
- [ ] 4. 编写 `.env` 文件（参考 `.env.example`，填入实际地址与密钥）
- [ ] 5. 构建镜像：`docker build -f Dockerfile -t llm_gate:latest .`
- [ ] 6. 启动容器：`docker run -d -p 9981:9981 --env-file .env llm_gate:latest`
- [ ] 7. 验证健康检查：`curl http://<host>:9981/health` 返回 `{"status":"healthy",...}`
- [ ] 8. 访问 `http://<host>:9981/` 登录（默认管理员 `gate_admin` / `qweasdzxc123321`）
- [ ] 9. 登录后立即修改管理员密码（通过前端或 API）
