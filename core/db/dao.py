# type: ignore
import abc
import traceback
from typing import List, Optional, Tuple

from core.db import DatabaseManager, connection
from core.db.utils import DatabaseError
from log_helper.async_logger import get_async_logger

logger = get_async_logger(__name__)


# TODO: Might complete it in the next refactoring
class BaseDAO(abc.ABC):
    version = None
    db_manager: Optional[DatabaseManager] = None

    def __init__(self) -> None:
        self.db_manager = connection

    def set_isolation_level(self, level: Optional[int]) -> None:
        self.db_manager.set_isolation_level(level)

    def has_returning_syntax(self, query: str) -> bool:
        returning_str = "RETURNING"
        return any([s in query for s in [returning_str, returning_str.lower()]])

    def get_list(self, query: str, *args) -> List[Tuple]:
        try:
            with self.db_manager.cursor() as cursor:
                cursor.execute(query, tuple(args))
                result = cursor.fetchall()
                if result is not None and isinstance(result, List) and len(result) > 0:
                    return result
                return []
        except Exception as exc:
            logger.debug(traceback.format_exc())
            raise DatabaseError(exc) from exc

    def get_one(self, query: str, *args) -> Optional[Tuple]:
        try:
            with self.db_manager.cursor() as cursor:
                cursor.execute(query, tuple(args))
                result = cursor.fetchone()
                if result is not None and isinstance(result, Tuple) and len(result) > 0:
                    return result
                return None

        except Exception as exc:
            logger.debug(traceback.format_exc())
            raise DatabaseError(exc) from exc

    def insert_one(self, query: str, *args) -> Optional[Tuple]:
        returning = self.has_returning_syntax(query)

        try:
            with self.db_manager.cursor() as cursor:
                cursor.execute(query, tuple(args))
                if returning:
                    result = cursor.fetchone()
                    if (
                        result is not None
                        and isinstance(result, Tuple)
                        and len(result) > 0
                    ):
                        return result
                return None

        except Exception as exc:
            logger.debug(traceback.format_exc())
            raise DatabaseError(exc) from exc
