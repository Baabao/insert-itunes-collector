import functools

from core.db import connection


def check_conn(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        connection.close_if_unusable_or_obsolete()
        result = func(*args, **kwargs)
        connection.close()
        return result

    return wrapper
