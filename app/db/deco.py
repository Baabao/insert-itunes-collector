import functools

from core.db import connection


def check_conn(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            connection.close_if_unusable_or_obsolete()
            return func(*args, **kwargs)
        finally:
            connection.close()

    return wrapper
