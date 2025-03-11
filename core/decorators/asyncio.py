import asyncio
import functools
from typing import Callable, Optional

from core.common.type_checker import is_processing_proxy
from core.utils.exceptions import SynchronousOnlyOperation
from log_helper.async_logger import get_async_logger

logger = get_async_logger(__name__)


def async_unsafe(message):
    """
    Decorator to mark functions as async-unsafe. Someone trying to access
    the function while in an async context will get an error message.
    """

    def decorator(func):
        @functools.wraps(func)
        def wrap(*args, **kwargs):
            # Detect a running event loop in this thread.
            try:
                event_loop = asyncio.get_event_loop()
            except RuntimeError:
                pass
            else:
                if event_loop.is_running():
                    raise SynchronousOnlyOperation(message)
            # Pass onwards.
            return func(*args, **kwargs)

        return wrap

    # If the message is actually a function, then be a no-arguments decorator.
    if callable(message):
        func = message
        message = "You cannot call this from an async context - use a thread or sync_to_async."
        return decorator(func)
    else:
        return decorator


def pop_args(index, *args):
    if index < 0 or index >= len(args):
        raise IndexError("args out of range")
    popped = args[index]
    remaining = args[:index] + args[index + 1 :]
    return popped, remaining


def async_safety(
    f: Optional[Callable] = None, *, via: bool = False, raise_error: bool = True
):
    def decorator(func):
        @functools.wraps(func)
        def wrap(*args, **kwargs):
            lock = kwargs.get("lock") or next(
                (arg for arg in args if is_processing_proxy(arg)), None
            )

            if not is_processing_proxy(lock):
                if raise_error:
                    raise ValueError(
                        "lock error, it must offer processing lock in kwargs"
                    )

                logger.debug("not working, it must offer processing lock in kwargs")
                return func(*args, **kwargs)

            if not via:
                try:
                    lock = kwargs.pop("lock")
                except KeyError:
                    index = next(
                        (i for i, arg in enumerate(args) if is_processing_proxy(arg)),
                        None,
                    )
                    lock, args = pop_args(index, *args)

            with lock:
                return func(*args, **kwargs)

        return wrap

    if callable(f):
        return decorator(f)
    else:
        return decorator
