from typing import Any, Callable, Dict, List, Optional

from core.common.type_checker import is_dict, is_list
from log_helper.async_logger import get_async_logger

logger = get_async_logger(__name__)


def apply_methods_to_get_first_match_result(
    try_methods: List[Callable], data: Dict, key: str
) -> Optional[Any]:
    for try_method in try_methods:
        try:
            return try_method(data, key)
        except Exception as exc:
            logger.debug("method throw error, method: %s, %s", try_method.__name__, exc)
    return None


def apply_methods_to_get_all_result(
    try_methods: List[Callable], data: Any
) -> List[Any]:
    result = []
    for try_method in try_methods:
        try:
            result.append(try_method(data))
        except Exception as exc:
            logger.debug("method throw error, method: %s, %s", try_method.__name__, exc)
    return result


def apply_method_with_list_to_get_all_result(
    items: List[Any], method: Callable
) -> List[Any]:
    result = []
    for item in items:
        try:
            if isinstance(item, tuple):
                result.append(method(*item))
            elif isinstance(item, dict):
                result.append(method(**item))
            else:
                result.append(method(item))
        except Exception as exc:
            logger.debug(
                "method throw error, method: %s, item: %s, %s",
                method.__name__,
                dir(item),
                exc,
            )
    return result


def find_item_with_key(items: List[Any], key: str) -> Optional[Any]:
    """
    Finds and returns the first dictionary in the list that contains the given key.
    Returns None if no such dictionary is found.
    """
    return next(
        (item for item in items if isinstance(item, dict) and item.get(key)), None
    )


def is_empty_dict(value: Any) -> bool:
    return is_dict(value) or not value


def is_empty_list(value: Any) -> bool:
    return is_list(value) and not value


def sort_list_by_key(
    items: List[Dict], key: str, default: Any = None, reverse: bool = False
) -> List[Dict]:
    if not isinstance(items, list):
        raise TypeError("items not a list type")
    return sorted(items, key=lambda d: d.get(key, default), reverse=reverse)
