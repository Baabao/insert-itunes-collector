import multiprocessing
import os
import traceback
from multiprocessing.pool import ThreadPool
from typing import Any, Optional

from app.crawler.exceptions import CrawlerUnavailable, FeedException
from log_helper.async_logger import get_async_logger

logger = get_async_logger(__name__)


def abort_wrapper(func, *args, **kwargs) -> Optional[Any]:
    timeout = kwargs.get("timeout", None)
    finally_executes = kwargs.get("finally_executes", [])

    thread = ThreadPool(1)
    res = thread.apply_async(func, args=args)
    out = None
    try:
        out = res.get(timeout)  # Wait timeout seconds for func to complete.
        thread.close()
        thread.join()

    except CrawlerUnavailable as _:
        logger.info(
            "aborting due to unavailable request, func: %s, pid: %s",
            func.__name__,
            os.getpid(),
        )

    except FeedException as _:
        logger.info(
            "failure to get feed, func: %s, pid: %s", func.__name__, os.getpid()
        )

    except multiprocessing.TimeoutError as _:
        logger.info(
            "aborting due to timeout, func: %s, pid: %s", func.__name__, os.getpid()
        )

    except Exception as _:
        logger.error(
            "unexpected aborting, func: %s , pid: %s, %s",
            func.__name__,
            os.getpid(),
            traceback.format_exc(10),
        )
    finally:
        thread.terminate()
        for func_dict in finally_executes:
            func = func_dict.get("func")
            arguments = func_dict.get("args", [])
            func(*arguments)
    return out
