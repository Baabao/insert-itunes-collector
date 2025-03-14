import functools

from core.db import connection


def check_conn(end_connection: bool = None):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                connection.close_if_unusable_or_obsolete()
                return func(*args, **kwargs)
            finally:
                if close:
                    connection.close()

        return wrapper

    close = None

    if callable(end_connection):
        f = end_connection
        return decorator(f)
    else:
        close = end_connection
        return decorator
