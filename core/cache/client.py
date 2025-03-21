import copy
import logging
import pickle
from typing import Any, Optional

import redis

from core.cache.exceptions import RedisConnectDbNumberError
from core.common.type_checker import is_picklable, is_unpicklable

logger = logging.getLogger(__name__)


# TODO: use cached_property to improve pickle things
class RedisClient:
    connection: Optional[redis.Redis] = None

    def __init__(
        self, endpoint: str, port: int = 6379, db_number: Optional[int] = None
    ):
        # Note: db=0, Django ; db=1, iTunes Daemon
        if not isinstance(db_number, int):
            raise TypeError(f"Redis db number must int type, db_number type: {type(db_number)}")
        if db_number < 0 or db_number > 15:
            raise RedisConnectDbNumberError(f"Redis db number out of range, db_number: {db_number}")

        self.pool = redis.ConnectionPool(host=endpoint, port=port, db=db_number)
        # Pool Observation
        logger.debug("init successful, pid: %s, id: %s", self.pool.pid, id(self.pool))

    @property
    def conn(self) -> redis.Redis:
        if self.connection is None:
            return self.get_connection()
        return self.connection

    def get_connection(self) -> redis.Redis:
        self.connection = redis.Redis(connection_pool=self.pool)
        return self.connection

    def get(self, name: str):
        data = self.conn.get(name)
        if is_unpicklable(data):
            return pickle.loads(data)
        return data

    def set(self, name: str, value: Any, timeout: int) -> bool:
        copy_value = copy.copy(value)
        if not is_picklable(copy_value):
            raise TypeError(f"The value is not picklable, value: {value}")
        pickle_value = pickle.dumps(copy_value)
        return self.conn.set(name, pickle_value, ex=timeout)
