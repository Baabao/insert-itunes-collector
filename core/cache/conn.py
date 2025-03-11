from typing import Dict

from core.cache.client import RedisClient
from core.conf import settings
from core.utils.singleton import SingletonInstance


class RedisConn(metaclass=SingletonInstance):
    _instances: Dict = {}

    @staticmethod
    def get_instance(db_name) -> RedisClient:
        instance = RedisConn._instances.get(db_name)
        if instance is None:
            instance = RedisClient(
                settings.CACHE.get("ENDPOINT"), settings.CACHE.get("PORT"), db_name
            )
            RedisConn._instances.update({db_name: instance})
        return instance


redis_conn = RedisConn()


def get_redis_conn(db_number: int = 0) -> RedisClient:
    return redis_conn.get_instance(db_number)
