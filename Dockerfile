# syntax=docker/dockerfile:1

# ==================== Stage 1: 构建前端 ====================
FROM node:18-alpine AS frontend-builder
WORKDIR /build
# 先拷贝依赖清单，利用层缓存
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
# 拷贝前端源码并构建
COPY frontend/ ./
RUN npm run build

# ==================== Stage 2: 后端运行时 ====================
FROM python:3.11-slim
WORKDIR /app

# 安装后端依赖
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# 拷贝后端代码
COPY app/ ./app/
COPY run.py ./

# 拷贝前端构建产物到 static/（由 FastAPI 静态托管，实现单镜像部署）
COPY --from=frontend-builder /build/build ./static

ENV LLM_GATE_APP_ENV=production
ENV PYTHONUNBUFFERED=1

EXPOSE 9981

# 启动服务（启动时自动建表 + 预置管理员）
CMD ["python", "run.py"]
