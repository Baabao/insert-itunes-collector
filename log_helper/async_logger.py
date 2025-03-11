# type: ignore
import logging
from functools import wraps

from config.loader import execution
from log_helper import setup_logging
from log_helper.aws_handler import FirehoseHandler
from log_helper.json_formatter import JsonFormatter


def get_async_logger(name: str) -> logging.Logger:
    """
    using for multiple thread or multiple process's function
    """
    setup_logging(execution.logger)
    logger = logging.getLogger(name)
    for handler in logger.handlers:
        _formatter = handler.formatter
        if isinstance(handler, FirehoseHandler) and isinstance(
            _formatter, JsonFormatter
        ):
            formatter = AsyncJsonFormatter(_formatter.fmt_dict, _formatter.datefmt)
        else:
            formatter = AsyncPrefixFormatter(_formatter._fmt, _formatter.datefmt)
        handler.setFormatter(formatter)
    return logging.getLogger(name)


class AsyncPrefixFormatter(logging.Formatter):
    def __init__(self, fmt, datefmt):
        super().__init__(fmt, datefmt)

    def format(self, record: logging.LogRecord) -> str:
        original_message = super().format(record)
        return f"@{original_message}"


class AsyncJsonFormatter(JsonFormatter):
    def __init__(self, fmt, datefmt):
        super().__init__(fmt, datefmt)

    def format(self, record: logging.LogRecord) -> str:
        record.message = f"@{record.message}"
        return super().format(record)


def async_logger_deco(name: str):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **{"async_logger": get_async_logger(name), **kwargs})

        return wrapper

    return decorator
