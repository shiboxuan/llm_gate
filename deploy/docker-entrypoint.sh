#!/bin/bash
# LLM Gate 容器入口：同时拉起 uvicorn（内部 127.0.0.1:8000）与 nginx（对外 9000/9981）
# 任一进程退出即退出容器，便于 docker 重启策略生效

python run.py &
UVCORN_PID=$!

nginx -g 'daemon off;' &
NGINX_PID=$!

# 收到 SIGTERM/SIGINT（docker stop）时终止两个子进程
trap 'kill $UVCORN_PID $NGINX_PID 2>/dev/null; exit' TERM INT

# 阻塞至任一子进程退出
wait -n $UVCORN_PID $NGINX_PID
EXIT_CODE=$?

# 清理另一个仍在运行的进程
kill $UVCORN_PID $NGINX_PID 2>/dev/null || true
exit $EXIT_CODE
