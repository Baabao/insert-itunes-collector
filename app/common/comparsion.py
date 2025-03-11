from typing import AnyStr

from core.common.string import to_utf8_string
from log_helper.async_logger import get_async_logger

logger = get_async_logger(__name__)


def check_equal_string(a: AnyStr, b: AnyStr):
    try:
        return to_utf8_string(a) == to_utf8_string(b)
    except Exception as exc:
        logger.debug("unexpected error, %s", exc)
        return False


def check_equal_list(a, b):
    try:
        return set(a) == set(b)
    except Exception as exc:
        logger.debug("unexpected error, %s", exc)
        return False
