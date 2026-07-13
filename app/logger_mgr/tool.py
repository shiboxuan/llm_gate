#! /usr/bin/env python3
# -*- coding: utf-8 -*-
# @Date    : 2025/6/11
# @Desc    :
import logging
import queue
import sys
import socket
from logging import handlers
from graypy import GELFUDPHandler, GELFTCPHandler, GELFHTTPHandler
from .formatters import ConsoleFormatter
from typing import Literal

LOG_RESERVED_KEYS = {
    "name", "msg", "args", "levelname", "levelno", "pathname",
    "filename", "module", "exc_info", "exc_text", "stack_info",
    "lineno", "funcName", "created", "msecs", "relativeCreated",
    "thread", "threadName", "process", "processName"
}

LOG_TYPE = Literal["debug", "info", "warning", "error", "critical"]


def safe_extra_fields(extra: dict) -> dict:
    result = {}
    if not extra:
        return result

    for k, v in extra.items():
        key = f"_{k}" if k in LOG_RESERVED_KEYS else k
        result[key] = v

    return result


def graylog_handler(protocol: str):
    if protocol.lower() not in ["tcp", "udp", "http"]:
        raise ValueError("协议错误")
    handler = {
        "udp": GELFUDPHandler,
        "tcp": GELFTCPHandler,
        "http": GELFHTTPHandler,
    }
    # return handler[protocol.lower()] #涉及到端口，所以必须严格返回
    return handler.get(protocol.lower(), GELFUDPHandler)


def console_handler():
    console_formatter = ConsoleFormatter(fmt="[%(asctime)s][%(levelname)s] %(message)s | %(extra)s")
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(console_formatter)
    return console_handler


def queue_handler(q: queue.Queue):
    queue_handler = handlers.QueueHandler(q)
    return queue_handler


def get_local_ip() -> str:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
    except Exception:
        ip = "Unknown Host"
    return ip


class SafeGraylogHandler(logging.Handler):
    def __init__(self, wrapped: logging.Handler):
        super().__init__()
        self.wrapped = wrapped

    def emit(self, record: logging.LogRecord):
        try:
            self.wrapped.emit(record)
        except Exception as e:
            print(f"[GraylogFallback] Emit to Graylog failed: {e}", file=sys.stderr)
