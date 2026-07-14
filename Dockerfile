# syntax=docker/dockerfile:1

# ==================== Stage 1: 构建前端 ====================
FROM node:18-alpine AS frontend-builder
WORKDIR /build
# 先拷贝依赖清单，利用层缓存（.dockerignore 已排除本地 node_modules/build，保证 npm ci 在干净环境执行）
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
# 拷贝前端源码并构建
COPY frontend/ ./
RUN npm run build

# ==================== Stage 2: 后端运行时 + nginx 反代 ====================
FROM python:3.11-slim
WORKDIR /app

# 安装 nginx（用于 9000/9981 端口分发与管理面/数据面隔离）
RUN apt-get update \
    && apt-get install -y --no-install-recommends nginx \
    && rm -rf /var/lib/apt/lists/*

# 安装后端依赖
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# 拷贝后端代码
COPY app/ ./app/
COPY run.py ./

# 拷贝生产环境配置到 /app/.env（pydantic-settings 运行时自动读取，运行容器无需 --env-file 注入）
COPY .env.production ./.env

# 拷贝前端构建产物到 static/（由 FastAPI 静态托管，实现单镜像部署）
COPY --from=frontend-builder /build/build ./static

# 拷贝 nginx 配置与启动入口
COPY deploy/nginx.conf /etc/nginx/nginx.conf
COPY deploy/docker-entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# uvicorn 退到容器内部 127.0.0.1:8000，由 nginx 反代到对外端口 9000（管理网页）/9981（路由服务）
ENV LLM_GATE_APP_ENV=production
ENV LLM_GATE_APP_HOST=127.0.0.1
ENV LLM_GATE_APP_PORT=8000
ENV PYTHONUNBUFFERED=1

EXPOSE 9000 9981

# 启动 uvicorn + nginx（uvicorn 启动时自动建表 + 预置管理员）
CMD ["/entrypoint.sh"]
