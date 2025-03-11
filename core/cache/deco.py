import functools
import hashlib
import json

from core.cache.conn import get_redis_conn
from core.conf import settings
from core.utils.exceptions import ImproperlyConfigured
from log_helper.async_logger import get_async_logger

logger = get_async_logger(__name__)


def _hash_args_kwargs(*args, **kwargs) -> str:
    data = json.dumps({"args": args, "kwargs": kwargs}, sort_keys=True)
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def apply_cache(key: str, db_number: int, timeout: int = 1200):
    """
    ref: https://stackoverflow.com/questions/5929107/decorators-with-parameters (Good Example!)
    """

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            if key == "":
                cache_key = func.__name__
            else:
                cache_key = key

            db = settings.CACHE.get("DB", {}).get(db_number)
            if db is None:
                raise ImproperlyConfigured("settings.Cache must set DB field")

            prefix = db.get("PREFIX") or settings.APP_NAME

            cache_key = f"{prefix}__{cache_key}__{_hash_args_kwargs(*args, **kwargs)}"

            conn = get_redis_conn(db_number)

            try:
                data = conn.get(cache_key)
                if data is not None:
                    return data
            except Exception as exc:
                logger.debug("get cache error, %s", exc)

            data = func(*args, **kwargs)

            try:
                conn.set(cache_key, data, timeout)
            except Exception as exc:
                logger.debug("set cache error, %s", exc)

            return data

        return wrapper

    return decorator
