#! /usr/bin/env python3
# -*- coding: utf-8 -*-
# @Author  : Claude
# @Date    : 2026/4/10
# @Desc    : HTTP 请求超时配置模块

"""
HTTP 请求超时配置模块

提供流式和非流式请求的超时配置
"""
import httpx

from app.config import get_settings


def get_stream_timeout() -> httpx.Timeout:
    """
    获取流式请求超时配置

    Returns:
        httpx.Timeout: 流式请求超时配置
    """
    settings = get_settings()
    timeout = httpx.Timeout(connect=settings.proxy_timeout_connect, read=settings.proxy_timeout_read_stream, write=settings.proxy_timeout_write, pool=settings.proxy_timeout_pool)
    return timeout


def get_non_stream_timeout() -> httpx.Timeout:
    """
    获取非流式请求超时配置

    Returns:
        httpx.Timeout: 非流式请求超时配置
    """
    settings = get_settings()
    timeout = httpx.Timeout(connect=settings.proxy_timeout_connect, read=settings.proxy_timeout_read_non_stream, write=settings.proxy_timeout_write, pool=settings.proxy_timeout_pool)
    return timeout
