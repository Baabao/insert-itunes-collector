import functools
import os
import time

from config.loader import execution
from core.common.type_checker import is_processing_proxy
from core.decorators.asyncio import async_safety
from log_helper.async_logger import get_async_logger

logger = get_async_logger(__name__)


def sql_lock_v2(unit: int):
    def decorator(func):
        @functools.wraps(func)
        def wrap(*args, **kwargs):
            sleep_dict = kwargs.pop("sleep_dict", None)
            if sleep_dict is None:
                raise TypeError("missing 1 required positional argument: 'sleep_dict'")
            if not is_processing_proxy(sleep_dict):
                raise TypeError(
                    "sleep_dict is not a Proxy type, sleep_dict type: %s"
                    % (type(sleep_dict),)
                )

            func_name = func.__name__
            pid = os.getpid()

            @async_safety
            def inner():
                try:
                    logger.debug("%s locked, %s", pid, func_name)
                    sleep_dict.update({"count": sleep_dict.get("count", 0) + unit})
                    return func(*args, **kwargs)
                finally:
                    sleep_time = execution.config.sql_lock_sleep_time
                    if sleep_dict.get("count", 0) > execution.config.sql_lock_limit:
                        logger.debug(
                            "%s ready to sleep (%s), %s", pid, sleep_time, func_name
                        )

                        time.sleep(sleep_time)
                        sleep_dict.update({"count": 0})
                    logger.debug("%s release, %s", os.getpid(), func.__name__)

            return inner()

        return wrap

    if callable(unit):
        f = unit
        unit = 1
        return decorator(f)
    else:
        return decorator


def sql_lock(func):
    @functools.wraps(func)
    def wrap(*args, **kwargs):
        lock = kwargs.pop("lock", None)
        if lock is None:
            raise TypeError("missing 1 required positional argument: 'lock'")

        sleep_dict = kwargs.pop("sleep_dict", None)
        if sleep_dict is None:
            raise TypeError("missing 1 required positional argument: 'sleep_dict'")

        try:
            lock.acquire()

            logger.debug("%s locked, %s", os.getpid(), func.__name__)

            sql_lock_insert_count = getattr(execution, "config").sql_lock_insert_count
            sql_lock_update_count = getattr(execution, "config").sql_lock_update_count
            sql_lock_remove_count = getattr(execution, "config").sql_lock_remove_count

            if str(func.__name__).startswith("insert"):
                sleep_dict.update(
                    {"count": sleep_dict.get("count", 0) + sql_lock_insert_count}
                )

            if str(func.__name__).startswith("update"):
                sleep_dict.update(
                    {"count": sleep_dict.get("count", 0) + sql_lock_update_count}
                )

            if str(func.__name__).startswith("remove"):
                # adjust to 18, because removing seems cost more db resources
                sleep_dict.update(
                    {"count": sleep_dict.get("count", 0) + sql_lock_remove_count}
                )

            return func(*args, **kwargs)

        finally:
            sql_lock_limit = execution.config.sql_lock_limit
            sql_lock_sleep_time = execution.config.sql_lock_sleep_time

            if sleep_dict.get("count", 0) > sql_lock_limit:
                logger.debug(
                    "%s ready to sleep (%s), %s",
                    os.getpid(),
                    sql_lock_sleep_time,
                    func.__name__,
                )

                time.sleep(sql_lock_sleep_time)
                sleep_dict.update({"count": 0})

            lock.release()

            logger.debug("%s release, %s", os.getpid(), func.__name__)

    return wrap
