import functools
from typing import List, Tuple, Union


def env_func(env: str, only: Union[str, List, Tuple]):
    if not isinstance(only, (list, tuple)):
        only = [str(only)]

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            if env not in only:
                return
            return func(*args, **kwargs)

        return wrapper

    return decorator
