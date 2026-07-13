#! /usr/bin/env python3
# -*- coding: utf-8 -*-
# @Date    : 2026/2/25
# @Desc    : 错误码枚举定义、消息映射、HTTP 状态码映射

from __future__ import annotations

from enum import IntEnum

"""
设计文档: docs/base/error_code_system.md
"""


class ErrorCode(IntEnum):
    """业务错误码枚举"""

    # 成功
    SUCCESS = 0

    # 通用错误 10000-10999
    PARAM_MISSING = 10001           # 缺少必要参数
    PARAM_INVALID = 10002           # 参数格式无效
    UNAUTHORIZED = 10003            # 未授权
    TOKEN_EXPIRED = 10004           # Token 已过期
    TOKEN_INVALID = 10005           # Token 无效
    FORBIDDEN = 10006               # 无权限访问
    RATE_LIMIT_EXCEEDED = 10007     # 请求过于频繁
    INTERNAL_ERROR = 10008          # 服务器内部错误

    # 用户相关错误 11000-11999
    USER_NOT_FOUND = 11001          # 用户不存在
    USER_DISABLED = 11002           # 用户被禁用
    USER_CREATE_FAILED = 11003      # 用户创建失败

    # 工具相关错误 12000-12999
    TOOL_NOT_FOUND = 12001          # 工具不存在
    TOOL_DISABLED = 12002           # 工具被禁用
    TOOL_TOKEN_INVALID = 12003      # 工具 Token 无效
    TOOL_CREATE_FAILED = 12004      # 工具创建失败
    TOOL_UPDATE_FAILED = 12005      # 工具更新失败
    TOOL_DELETE_FAILED = 12006      # 工具删除失败
    TOOL_NAME_DUPLICATE = 12007     # 工具名称重复

    # 路由相关错误 13000-13999
    ROUTE_NOT_FOUND = 13001         # 路由不存在
    ROUTE_NOT_ACTIVE = 13002        # 无激活路由
    ROUTE_CREATE_FAILED = 13003     # 路由创建失败
    ROUTE_UPDATE_FAILED = 13004     # 路由更新失败
    ROUTE_DELETE_FAILED = 13005     # 路由删除失败
    ROUTE_NAME_DUPLICATE = 13006    # 路由名称重复

    # Provider Key 错误 14000-14999
    PROVIDER_KEY_NOT_FOUND = 14001      # Provider Key 不存在
    PROVIDER_KEY_DECRYPT_FAILED = 14002 # Provider Key 解密失败
    PROVIDER_KEY_CREATE_FAILED = 14003  # Provider Key 创建失败
    PROVIDER_KEY_NAME_DUPLICATE = 14004 # Provider Key 名称重复

    # 代理请求错误 15000-15999
    PROXY_REQUEST_FAILED = 15001    # 代理请求失败
    PROXY_TIMEOUT = 15002           # 代理请求超时
    PROXY_RESPONSE_INVALID = 15003  # 代理响应格式无效
    PROVIDER_ERROR = 15004          # Provider 返回错误（通用）
    PROVIDER_BAD_REQUEST = 15005    # Provider 400 错误（请求格式/参数错误）
    PROVIDER_AUTH_ERROR = 15006     # Provider 401/403 错误（认证/授权失败）
    PROVIDER_NOT_FOUND = 15007      # Provider 404 错误（模型/资源不存在）
    PROVIDER_RATE_LIMIT = 15008     # Provider 429 错误（限流）
    PROVIDER_SERVER_ERROR = 15009   # Provider 5xx 错误（上游服务器错误）

    # 缓存错误 16000-16999
    REDIS_CONNECTION_FAILED = 16001 # Redis 连接失败
    REDIS_OPERATION_FAILED = 16002  # Redis 操作失败

    # 数据库代理错误 17000-17999
    DB_PROXY_CONNECTION_FAILED = 17001  # 数据库代理连接失败
    DB_PROXY_QUERY_FAILED = 17002       # 数据库查询失败
    DB_PROXY_EXECUTE_FAILED = 17003     # 数据库执行失败


# 错误消息映射
ERROR_MESSAGES: dict[ErrorCode, str] = {
    # 成功
    ErrorCode.SUCCESS: "ok",

    # 通用错误
    ErrorCode.PARAM_MISSING: "缺少必要参数",
    ErrorCode.PARAM_INVALID: "参数格式无效",
    ErrorCode.UNAUTHORIZED: "未授权",
    ErrorCode.TOKEN_EXPIRED: "Token 已过期",
    ErrorCode.TOKEN_INVALID: "Token 无效",
    ErrorCode.FORBIDDEN: "无权限访问",
    ErrorCode.RATE_LIMIT_EXCEEDED: "请求过于频繁，请稍后重试",
    ErrorCode.INTERNAL_ERROR: "服务器内部错误",

    # 用户相关错误
    ErrorCode.USER_NOT_FOUND: "用户不存在",
    ErrorCode.USER_DISABLED: "用户被禁用",
    ErrorCode.USER_CREATE_FAILED: "用户创建失败",

    # 工具相关错误
    ErrorCode.TOOL_NOT_FOUND: "工具不存在",
    ErrorCode.TOOL_DISABLED: "工具被禁用",
    ErrorCode.TOOL_TOKEN_INVALID: "工具 Token 无效",
    ErrorCode.TOOL_CREATE_FAILED: "工具创建失败",
    ErrorCode.TOOL_UPDATE_FAILED: "工具更新失败",
    ErrorCode.TOOL_DELETE_FAILED: "工具删除失败",
    ErrorCode.TOOL_NAME_DUPLICATE: "工具名称重复",

    # 路由相关错误
    ErrorCode.ROUTE_NOT_FOUND: "路由不存在",
    ErrorCode.ROUTE_NOT_ACTIVE: "无激活路由",
    ErrorCode.ROUTE_CREATE_FAILED: "路由创建失败",
    ErrorCode.ROUTE_UPDATE_FAILED: "路由更新失败",
    ErrorCode.ROUTE_DELETE_FAILED: "路由删除失败",
    ErrorCode.ROUTE_NAME_DUPLICATE: "路由名称重复",

    # Provider Key 错误
    ErrorCode.PROVIDER_KEY_NOT_FOUND: "Provider Key 不存在",
    ErrorCode.PROVIDER_KEY_DECRYPT_FAILED: "Provider Key 解密失败",
    ErrorCode.PROVIDER_KEY_CREATE_FAILED: "Provider Key 创建失败",
    ErrorCode.PROVIDER_KEY_NAME_DUPLICATE: "Provider Key 名称重复",

    # 代理请求错误
    ErrorCode.PROXY_REQUEST_FAILED: "代理请求失败",
    ErrorCode.PROXY_TIMEOUT: "代理请求超时",
    ErrorCode.PROXY_RESPONSE_INVALID: "代理响应格式无效",
    ErrorCode.PROVIDER_ERROR: "Provider 返回错误",
    ErrorCode.PROVIDER_BAD_REQUEST: "Provider 请求参数错误",
    ErrorCode.PROVIDER_AUTH_ERROR: "Provider 认证失败",
    ErrorCode.PROVIDER_NOT_FOUND: "Provider 资源不存在",
    ErrorCode.PROVIDER_RATE_LIMIT: "Provider 限流",
    ErrorCode.PROVIDER_SERVER_ERROR: "Provider 服务器错误",

    # 缓存错误
    ErrorCode.REDIS_CONNECTION_FAILED: "Redis 连接失败",
    ErrorCode.REDIS_OPERATION_FAILED: "Redis 操作失败",

    # 数据库代理错误
    ErrorCode.DB_PROXY_CONNECTION_FAILED: "数据库代理连接失败",
    ErrorCode.DB_PROXY_QUERY_FAILED: "数据库查询失败",
    ErrorCode.DB_PROXY_EXECUTE_FAILED: "数据库执行失败",
}


# HTTP 状态码映射
HTTP_STATUS_MAP: dict[ErrorCode, int] = {
    # 成功
    ErrorCode.SUCCESS: 200,

    # 400 Bad Request
    ErrorCode.PARAM_MISSING: 400,
    ErrorCode.PARAM_INVALID: 400,
    ErrorCode.ROUTE_NOT_ACTIVE: 400,

    # 401 Unauthorized
    ErrorCode.UNAUTHORIZED: 401,
    ErrorCode.TOKEN_EXPIRED: 401,
    ErrorCode.TOKEN_INVALID: 401,
    ErrorCode.TOOL_TOKEN_INVALID: 401,

    # 403 Forbidden
    ErrorCode.FORBIDDEN: 403,
    ErrorCode.USER_DISABLED: 403,
    ErrorCode.TOOL_DISABLED: 403,

    # 404 Not Found
    ErrorCode.USER_NOT_FOUND: 404,
    ErrorCode.TOOL_NOT_FOUND: 404,
    ErrorCode.ROUTE_NOT_FOUND: 404,
    ErrorCode.PROVIDER_KEY_NOT_FOUND: 404,

    # 409 Conflict
    ErrorCode.TOOL_NAME_DUPLICATE: 409,
    ErrorCode.ROUTE_NAME_DUPLICATE: 409,
    ErrorCode.PROVIDER_KEY_NAME_DUPLICATE: 409,

    # 429 Too Many Requests
    ErrorCode.RATE_LIMIT_EXCEEDED: 429,

    # 400 Bad Request - 业务逻辑拒绝
    ErrorCode.ROUTE_DELETE_FAILED: 400,  # 删除激活路由等业务逻辑拒绝

    # 500 Internal Server Error
    ErrorCode.INTERNAL_ERROR: 500,
    ErrorCode.USER_CREATE_FAILED: 500,
    ErrorCode.TOOL_CREATE_FAILED: 500,
    ErrorCode.TOOL_UPDATE_FAILED: 500,
    ErrorCode.TOOL_DELETE_FAILED: 500,
    ErrorCode.ROUTE_CREATE_FAILED: 500,
    ErrorCode.ROUTE_UPDATE_FAILED: 500,
    ErrorCode.PROVIDER_KEY_DECRYPT_FAILED: 500,
    ErrorCode.PROVIDER_KEY_CREATE_FAILED: 500,
    ErrorCode.REDIS_CONNECTION_FAILED: 500,
    ErrorCode.REDIS_OPERATION_FAILED: 500,
    ErrorCode.DB_PROXY_CONNECTION_FAILED: 500,
    ErrorCode.DB_PROXY_QUERY_FAILED: 500,
    ErrorCode.DB_PROXY_EXECUTE_FAILED: 500,

    # 502 Bad Gateway
    ErrorCode.PROXY_REQUEST_FAILED: 502,
    ErrorCode.PROXY_RESPONSE_INVALID: 502,
    ErrorCode.PROVIDER_ERROR: 502,
    ErrorCode.PROVIDER_BAD_REQUEST: 502,      # 透传上游 400 错误
    ErrorCode.PROVIDER_AUTH_ERROR: 502,       # 透传上游 401/403 错误
    ErrorCode.PROVIDER_NOT_FOUND: 502,        # 透传上游 404 错误
    ErrorCode.PROVIDER_SERVER_ERROR: 502,     # 透传上游 5xx 错误

    # 504 Gateway Timeout
    ErrorCode.PROXY_TIMEOUT: 504,

    # 429 Too Many Requests（透传上游限流）
    ErrorCode.PROVIDER_RATE_LIMIT: 429,
}


def get_http_status(code: ErrorCode) -> int:
    """根据错误码获取对应的 HTTP 状态码，未映射的默认返回 500"""
    return HTTP_STATUS_MAP.get(code, 500)


def get_error_message(code: ErrorCode) -> str:
    """根据错误码获取对应的错误消息，未映射的默认返回 '未知错误'"""
    return ERROR_MESSAGES.get(code, "未知错误")
