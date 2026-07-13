#! /usr/bin/env python3
# -*- coding: utf-8 -*-
# @Date    : 2025/6/11
# @Desc    :
import atexit
import logging
import sys
import threading
import traceback
from typing import Any, Callable, Dict, List, Optional

from app.config import get_settings

from .tool import (
    LOG_TYPE,
    SafeGraylogHandler,
    console_handler,
    get_local_ip,
    graylog_handler,
    handlers,
    queue,
    safe_extra_fields,
)


class GraylogProxy(object):
    _instances: Dict[str, "GraylogProxy"] = {}
    _lock = threading.Lock()

    def __new__(cls, protocol: str, *args, **kwargs):
        with cls._lock:
            if protocol not in cls._instances:
                instance = super().__new__(cls)
                cls._instances[protocol] = instance
            return cls._instances[protocol]

    def __init__(
        self,
        protocol: str,
        *,
        business: str,
        default_fields: dict = None,
        host: str = "localhost",
        port: int = None,
        level: str = "INFO",
        queue_max_limit: int = -1,
        console_handler_func: Optional[Callable[[], logging.Handler]] = console_handler,
    ):
        with self.__class__._lock:
            if hasattr(self, "_initialized"):
                return
            self._initialized = True

        self.q = queue.Queue(queue_max_limit)
        self.logger = logging.getLogger(f"{business}_{protocol}_logger")
        self.logger.setLevel(getattr(logging, level.upper(), logging.INFO))
        self.logger.addHandler(handlers.QueueHandler(self.q))
        self.logger.propagate = False
        self.default_fields = {"business": business, "ip": get_local_ip()}
        if default_fields:
            self.default_fields.update(default_fields)

        if console_handler_func:
            _console_handler = console_handler_func()
        else:
            _console_handler = None

        handlers_to_use: List[logging.Handler] = []
        if port:
            _graylog_handler = SafeGraylogHandler(graylog_handler(protocol)(host, port))
        else:
            _graylog_handler = SafeGraylogHandler(graylog_handler(protocol)(host))
        handlers_to_use.append(_graylog_handler)

        if _console_handler:
            handlers_to_use.append(_console_handler)

        self.listener = handlers.QueueListener(self.q, *handlers_to_use)
        self.listener.start()
        atexit.register(self._shutdown)

    def _shutdown(self):
        if hasattr(self, "listener"):
            self.listener.stop()

    def _normalize_message(self, message: Any, args: tuple) -> str:
        if not args:
            return str(message)
        try:
            return str(message) % args
        except Exception:
            return " ".join([str(message), *[str(arg) for arg in args]])

    def _build_extra_fields(
        self,
        base_extra: Optional[dict] = None,
        extra_fields: Optional[dict] = None,
        exc_info: Any = None,
        stack_info: bool = False,
    ) -> dict:
        full_fields = {**self.default_fields}
        if base_extra:
            full_fields.update(base_extra)
        if extra_fields:
            full_fields.update(extra_fields)

        if exc_info:
            if exc_info is True:
                exc_info = sys.exc_info()
            if isinstance(exc_info, tuple) and exc_info[0] is not None:
                full_fields["exception_type"] = exc_info[0].__name__
                full_fields["exception_message"] = str(exc_info[1])
                full_fields["traceback"] = "".join(traceback.format_exception(*exc_info))

        if stack_info:
            full_fields["stack_info"] = "".join(traceback.format_stack())

        return safe_extra_fields(full_fields)

    def _log(
        self,
        level: LOG_TYPE,
        message: Any,
        *args,
        extra: Optional[dict] = None,
        exc_info: Any = None,
        stack_info: bool = False,
        stacklevel: int = 3,
        **kwargs,
    ):
        level = level.lower()
        levelno = getattr(logging, level.upper(), None)
        if levelno is None:
            raise ValueError(f"Unsupported log level: {level}")

        log_message = self._normalize_message(message, args)
        merged_extra = self._build_extra_fields(
            extra_fields=extra,
            exc_info=exc_info,
            stack_info=stack_info,
        )
        if kwargs:
            merged_extra.update(safe_extra_fields(kwargs))

        self.logger.log(levelno, log_message, extra=merged_extra, stacklevel=stacklevel)

    def debug(self, message: Any, *args, **kwargs):
        self._log("debug", message, *args, stacklevel=4, **kwargs)

    def info(self, message: Any, *args, **kwargs):
        self._log("info", message, *args, stacklevel=4, **kwargs)

    def warning(self, message: Any, *args, **kwargs):
        self._log("warning", message, *args, stacklevel=4, **kwargs)

    def error(self, message: Any, *args, **kwargs):
        self._log("error", message, *args, stacklevel=4, **kwargs)

    def critical(self, message: Any, *args, **kwargs):
        self._log("critical", message, *args, stacklevel=4, **kwargs)

    def exception(self, message: Any, *args, **kwargs):
        kwargs.setdefault("exc_info", True)
        self._log("error", message, *args, stacklevel=4, **kwargs)

    def make_custom_logger(self, **kwargs):
        """
        创建一个自定义子logger，可以设置每次都需要传入的字段
        :param kwargs:
        :return:
        """
        return SubLogger(self, **kwargs)


class SubLogger:
    def __init__(self, log_instance: GraylogProxy, **kwargs):
        self.log_instance = log_instance
        self.base_fields = kwargs

    def _merge_kwargs(self, kwargs: dict) -> dict:
        kwargs = dict(kwargs)
        extra = kwargs.pop("extra", {}) or {}
        kwargs["extra"] = {**self.base_fields, **extra}
        return kwargs

    def info(self, msg, *args, **kwargs):
        self.log_instance.info(msg, *args, **self._merge_kwargs(kwargs))

    def debug(self, msg: str, *args, **kwargs):
        self.log_instance.debug(msg, *args, **self._merge_kwargs(kwargs))

    def warning(self, msg: str, *args, **kwargs):
        self.log_instance.warning(msg, *args, **self._merge_kwargs(kwargs))

    def error(self, msg: str, *args, **kwargs):
        self.log_instance.error(msg, *args, **self._merge_kwargs(kwargs))

    def critical(self, msg: str, *args, **kwargs):
        self.log_instance.critical(msg, *args, **self._merge_kwargs(kwargs))

    def exception(self, msg: str, *args, **kwargs):
        self.log_instance.exception(msg, *args, **self._merge_kwargs(kwargs))


def _build_root_logger() -> GraylogProxy:
    settings = get_settings()
    default_fields = {
        "service": settings.app_name,
        "app_env": settings.app_env,
    }
    return GraylogProxy(
        settings.graylog_protocol,
        business=settings.graylog_business,
        default_fields=default_fields,
        host=settings.graylog_host,
        port=settings.graylog_port,
        level=settings.graylog_level,
        console_handler_func=console_handler,
    )


def get_logger(name: Optional[str] = None, **default_fields) -> SubLogger:
    base_logger = _build_root_logger()
    merged_fields = {}
    if name:
        merged_fields["logger_name"] = name
    if default_fields:
        merged_fields.update(default_fields)
    return base_logger.make_custom_logger(**merged_fields)


logger = get_logger("llm_gate")