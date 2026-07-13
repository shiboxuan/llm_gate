#! /usr/bin/env python3
# -*- coding: utf-8 -*-
# @Date    : 2025/6/11
# @Desc    :
import logging


class ExtraFormatter(logging.Formatter):
    def format(self, record):
        standard_attrs = logging.LogRecord(None, None, "", 0, "", (), None).__dict__
        extra_data = {}
        for key, value in record.__dict__.items():
            if key not in standard_attrs and key not in ["message", "ip", "business"]:
                extra_data[key] = value

        record.extra = extra_data
        return super().format(record)


class ConsoleFormatter(ExtraFormatter):
    pass
