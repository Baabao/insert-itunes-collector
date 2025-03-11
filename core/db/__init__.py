# pylint: disable=no-name-in-module, multiple-statements, fixme, line-too-long
from psycopg2._psycopg import Error as DatabaseException

from core.conf import settings
from core.utils.lazy import LazyObject

from .manager import DatabaseConnection, DatabaseManager

__all__ = ["DatabaseException", "DatabaseManager", "DatabaseConnection", "connection"]


class Connection(LazyObject):
    def _setup(self):
        self._wrapped = DatabaseManager(settings.DATABASE)
        # Note: allow thread sharing, cause already lock CUD with lock decorator each sql operation
        self._wrapped.inc_thread_sharing()


connection = Connection()
