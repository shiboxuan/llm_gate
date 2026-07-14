#! /usr/bin/env python3
# -*- coding: utf-8 -*-
# @Author  : LLM Gate
# @Date    : 2026/2/26
# @Desc    : 应用启动脚本

import asyncio
import uvicorn
from app.config import get_settings


def init_database():
    """在主进程中初始化数据库（避免多 worker 竞争）"""
    from app.services.db_init_service import ensure_database_ready
    asyncio.run(ensure_database_ready())


if __name__ == "__main__":
    settings = get_settings()
    print("Debug模式 >>> :", settings.debug)
    
    # 在启动 workers 之前初始化数据库（仅主进程执行）
    print("正在初始化数据库...")
    init_database()
    print("数据库初始化完成")
    
    uvicorn.run(
        "app.main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=settings.debug,
        log_level="info" if settings.debug else "warning",
        access_log=settings.debug,
        workers=1 if settings.debug else 4,
        # workers=1
    )
