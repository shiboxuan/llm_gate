#!/bin/bash
# ============================================================
# LLM Gate 一体化镜像入口：PostgreSQL + Redis + uvicorn + nginx 同容器启动
#
# 数据持久化：把宿主机目录挂载到 $LLM_GATE_PG_DATA / $LLM_GATE_REDIS_DATA 即可。
# 可配置环境变量（均有默认值，默认与 .env.production 对应）：
#   LLM_GATE_PG_DATA        PostgreSQL 数据目录（容器内挂载点，默认 /var/lib/postgresql/data）
#   LLM_GATE_REDIS_DATA     Redis 数据目录（容器内挂载点，默认 /var/lib/redis）
#   LLM_GATE_DB_USER / LLM_GATE_DB_PASSWORD / LLM_GATE_DB_NAME  数据库账号（默认 llm_gate/llm_gate/llm_gate）
#   LLM_GATE_DB_PORT / LLM_GATE_REDIS_PORT   端口（默认 5432 / 6379）
# ============================================================
set -e

# ==================== 配置 ====================
PG_DATA="${LLM_GATE_PG_DATA:-/var/lib/postgresql/data}"
REDIS_DATA="${LLM_GATE_REDIS_DATA:-/var/lib/redis}"
DB_USER="${LLM_GATE_DB_USER:-llm_gate}"
DB_PASSWORD="${LLM_GATE_DB_PASSWORD:-llm_gate}"
DB_NAME="${LLM_GATE_DB_NAME:-llm_gate}"
DB_PORT="${LLM_GATE_DB_PORT:-5432}"
REDIS_PORT="${LLM_GATE_REDIS_PORT:-6379}"

# 数据库标识符合法性检查（防止 SQL 注入）
echo "${DB_USER}${DB_NAME}" | grep -Eq '^[A-Za-z0-9_]+$' || {
    echo "[FATAL] DB_USER / DB_NAME 仅允许字母、数字、下划线" >&2
    exit 1
}

# 自动探测 PostgreSQL 版本目录（如 /usr/lib/postgresql/15/bin）
PG_BIN="$(ls -d /usr/lib/postgresql/*/bin 2>/dev/null | head -n1)"
[ -n "$PG_BIN" ] || { echo "[FATAL] 未找到 PostgreSQL" >&2; exit 1; }

# ==================== PostgreSQL ====================
echo "==> [PostgreSQL] 数据目录: $PG_DATA"
mkdir -p "$PG_DATA"
chown -R postgres:postgres "$PG_DATA"

# 首次启动（目录为空）时初始化数据目录
if [ ! -s "$PG_DATA/PG_VERSION" ]; then
    echo "==> [PostgreSQL] 首次启动，执行 initdb ..."
    runuser -u postgres -- "$PG_BIN/initdb" -D "$PG_DATA" --encoding=UTF8 --auth-local=trust --auth-host=trust
fi

echo "==> [PostgreSQL] 启动 (127.0.0.1:$DB_PORT)"
runuser -u postgres -- "$PG_BIN/pg_ctl" -D "$PG_DATA" -o "-c listen_addresses=127.0.0.1 -c port=$DB_PORT" -l /tmp/postgres.log start

# 等待 PostgreSQL 就绪
for _ in $(seq 1 60); do
    if runuser -u postgres -- "$PG_BIN/pg_isready" -h 127.0.0.1 -p "$DB_PORT" >/dev/null 2>&1; then
        break
    fi
    sleep 1
done

# 幂等创建角色与数据库（与 .env.production 的 DATABASE_URL 对应）
if ! runuser -u postgres -- "$PG_BIN/psql" -h 127.0.0.1 -p "$DB_PORT" -U postgres -tAc "SELECT 1 FROM pg_roles WHERE rolname='$DB_USER'" | grep -q 1; then
    echo "==> [PostgreSQL] 创建角色 $DB_USER"
    runuser -u postgres -- "$PG_BIN/psql" -h 127.0.0.1 -p "$DB_PORT" -U postgres -c "CREATE ROLE $DB_USER LOGIN PASSWORD '$DB_PASSWORD'"
fi
if ! runuser -u postgres -- "$PG_BIN/psql" -h 127.0.0.1 -p "$DB_PORT" -U postgres -tAc "SELECT 1 FROM pg_database WHERE datname='$DB_NAME'" | grep -q 1; then
    echo "==> [PostgreSQL] 创建数据库 $DB_NAME (owner=$DB_USER)"
    runuser -u postgres -- "$PG_BIN/psql" -h 127.0.0.1 -p "$DB_PORT" -U postgres -c "CREATE DATABASE $DB_NAME OWNER $DB_USER"
fi

# ==================== Redis ====================
echo "==> [Redis] 数据目录: $REDIS_DATA（AOF 持久化开启）"
mkdir -p "$REDIS_DATA"
chown -R redis:redis "$REDIS_DATA"
redis-server --bind 127.0.0.1 --port "$REDIS_PORT" --dir "$REDIS_DATA" --appendonly yes --daemonize no &
REDIS_PID=$!

# ==================== 应用 + nginx ====================
python run.py &
UVCORN_PID=$!
nginx -g 'daemon off;' &
NGINX_PID=$!

# 收到 SIGTERM/SIGINT（docker stop）时优雅退出
cleanup() {
    kill "$UVCORN_PID" "$NGINX_PID" "$REDIS_PID" 2>/dev/null || true
    runuser -u postgres -- "$PG_BIN/pg_ctl" -D "$PG_DATA" stop -m fast 2>/dev/null || true
    exit 0
}
trap 'cleanup' TERM INT

# 阻塞至任一子进程退出（任一进程挂掉即退出容器，便于重启策略生效）
wait -n "$UVCORN_PID" "$NGINX_PID" "$REDIS_PID"
EXIT_CODE=$?
kill "$UVCORN_PID" "$NGINX_PID" "$REDIS_PID" 2>/dev/null || true
runuser -u postgres -- "$PG_BIN/pg_ctl" -D "$PG_DATA" stop -m fast 2>/dev/null || true
exit "$EXIT_CODE"
