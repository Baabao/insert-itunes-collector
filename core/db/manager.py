# pylint: disable=no-name-in-module
# type: ignore
import _thread
import os
import re
import threading
import time
from contextlib import contextmanager
from functools import cached_property
from typing import Dict, Optional

from core.db.cursor_wrapper import CursorWrapper
from core.db.transaction import TransactionManagementError
from core.db.utils import DatabaseError, DatabaseErrorWrapper, Error
from core.utils.exceptions import ImproperlyConfigured
from core.utils.singleton import SingletonInstance

try:
    import psycopg2
    import psycopg2.extensions
    import psycopg2.extras
    from psycopg2._psycopg import connection as DatabaseConnection

except ImportError as e:
    raise ImproperlyConfigured("Error loading psycopg2 module: %s" % e)


# Note: no use async_unsafe function, cause already control single thread outside
class DatabaseManager(metaclass=SingletonInstance):
    connection: Optional[DatabaseConnection] = None
    config_dict: Dict = None
    Database = psycopg2
    uses_savepoints = True

    def __init__(self, config: Dict):
        self.config_dict = config
        self.check_config_dict()

        self.isolation_level = None

        self.autocommit = False
        self.in_atomic_block = False

        self.savepoint_state = 0
        self.savepoint_ids = []

        self.commit_on_exit = True
        self.needs_rollback = False
        self.close_at = None
        self.closed_in_transaction = False
        self.errors_occurred = False

        self.run_on_commit = []
        self.run_commit_hooks_on_set_autocommit_on = False

        self.execute_wrappers = []

        self._thread_sharing_lock = threading.Lock()
        self._thread_sharing_count = 0
        self._thread_ident = _thread.get_ident()

    def check_config_dict(self) -> bool:
        if not isinstance(self.config_dict, dict):
            raise TypeError(
                f"Incorrect type, settings.DATABASE type: {type(self.config_dict)}"
            )
        config_keys = self.config_dict.keys()
        if "DSN" not in config_keys:
            raise KeyError("Require DSN in settings.DATABASE")
        return True

    def ensure_connection(self):
        """Guarantee that a connection to the database is established."""
        if self.connection is None:
            with self.wrap_database_errors:
                self.connect()

    def connect(self):
        """Connect to the database. Assume that the connection is closed."""
        self.check_config_dict()
        # In case the previous connection was closed while in an atomic block
        self.in_atomic_block = False
        self.savepoint_ids = []
        self.needs_rollback = False
        # Reset parameters defining when to close the connection
        max_age = self.config_dict["CONN_MAX_AGE"]
        self.close_at = None if max_age is None else time.monotonic() + max_age
        self.closed_in_transaction = False
        self.errors_occurred = False
        # Establish the connection
        connection_params = self.get_connection_params()
        self.connection = self.get_new_connection(connection_params)
        self.set_autocommit(self.config_dict["AUTOCOMMIT"])
        self.init_connection_state()
        self.run_on_commit = []

    # def close(self):
    #     if self.connection is not None:
    #         with self.wrap_database_errors:
    #
    #             return self.connection.close()

    def close(self):
        """Close the connection to the database."""
        self.validate_thread_sharing()
        self.run_on_commit = []

        # Don't call validate_no_atomic_block() to avoid making it difficult
        # to get rid of a connection in an invalid state. The next connect()
        # will reset the transaction state anyway.
        if self.closed_in_transaction or self.connection is None:
            return
        try:
            self._close()
        finally:
            if self.in_atomic_block:
                self.closed_in_transaction = True
                self.needs_rollback = True
            else:
                self.connection = None

    def is_usable(self):
        try:
            # Use a psycopg cursor directly, bypassing Django's utilities.
            self.connection.cursor().execute("SELECT 1")
        except Error:
            return False
        else:
            return True

    def close_if_unusable_or_obsolete(self):
        if self.connection is not None:
            # If the application didn't restore the original autocommit setting,
            # don't take chances, drop the connection.
            if self.get_autocommit() != self.config_dict["AUTOCOMMIT"]:
                self.close()
                return

            # If an exception other than DataError or IntegrityError occurred
            # since the last commit / rollback, check if the connection works.
            if self.errors_occurred:
                if self.is_usable():
                    self.errors_occurred = False
                else:
                    self.close()
                    return

            if self.close_at is not None and time.monotonic() >= self.close_at:
                self.close()
                return

    def get_isolation_level(self) -> int:
        return self.connection.isolation_level

    def set_isolation_level(self, level: Optional[int]) -> None:
        self.connection.set_isolation_level(level)

    def init_connection_state(self):
        self.connection.set_client_encoding("UTF8")

    def run_and_clear_commit_hooks(self):
        self.validate_no_atomic_block()
        current_run_on_commit = self.run_on_commit
        self.run_on_commit = []
        while current_run_on_commit:
            sids, func = current_run_on_commit.pop(0)
            func()

    def make_cursor(self, cursor) -> CursorWrapper:
        return CursorWrapper(cursor, self)

    def create_cursor(self, name=None):
        if name:
            cursor = self.connection.cursor(name, withhold=self.connection.autocommit)
        else:
            cursor = self.connection.cursor()
        return cursor

    @cached_property
    def wrap_database_errors(self) -> DatabaseErrorWrapper:
        return DatabaseErrorWrapper(self)

    # ### Thread ###
    @property
    def allow_thread_sharing(self):
        with self._thread_sharing_lock:
            return self._thread_sharing_count > 0

    def inc_thread_sharing(self):
        with self._thread_sharing_lock:
            self._thread_sharing_count += 1

    def dec_thread_sharing(self):
        with self._thread_sharing_lock:
            if self._thread_sharing_count <= 0:
                raise RuntimeError(
                    "Cannot decrement the thread sharing count below zero."
                )
            self._thread_sharing_count -= 1

    def validate_thread_sharing(self):
        """
        Validate that the connection isn't accessed by another thread than the
        one which originally created it, unless the connection was explicitly
        authorized to be shared between threads (via the `inc_thread_sharing()`
        method). Raise an exception if the validation fails.
        """
        if not (self.allow_thread_sharing or self._thread_ident == _thread.get_ident()):
            raise DatabaseError(
                "DatabaseWrapper objects created in a "
                "thread can only be used in that same thread. The object "
                "was created in thread id %s and this is thread id %s."
                % (self._thread_ident, _thread.get_ident())
            )

    # ### validation methods ###

    @contextmanager
    def execute_wrapper(self, wrapper):
        """
        Return a context manager under which the wrapper is applied to suitable
        database query executions.
        """
        self.execute_wrappers.append(wrapper)
        try:
            yield
        finally:
            self.execute_wrappers.pop()

    def _prepare_cursor(self, cursor) -> CursorWrapper:
        """
        Validate the connection is usable and perform database cursor wrapping.
        """
        self.validate_thread_sharing()
        return self.make_cursor(cursor)

    def _cursor(self, name=None) -> CursorWrapper:
        self.ensure_connection()
        return self._prepare_cursor(self.create_cursor(name))

    def _commit(self):
        if self.connection is not None:
            with self.wrap_database_errors:
                return self.connection.commit()

    def _rollback(self):
        if self.connection is not None:
            with self.wrap_database_errors:
                return self.connection.rollback()

    def _close(self):
        if self.connection is not None:
            with self.wrap_database_errors:
                return self.connection.close()

    # ### connection methods wrapper https://peps.python.org/pep-0249/#connection-objects ###

    def cursor(self) -> CursorWrapper:
        """Create a cursor, opening a connection if necessary."""
        return self._cursor()

    def commit(self):
        """Commit a transaction and reset the dirty flag."""
        self.validate_thread_sharing()
        self.validate_no_atomic_block()
        self._commit()
        # A successful commit means that the database connection works.
        self.errors_occurred = False
        self.run_commit_hooks_on_set_autocommit_on = True

    def rollback(self):
        """Roll back a transaction and reset the dirty flag."""
        self.validate_thread_sharing()
        self.validate_no_atomic_block()
        self._rollback()
        # A successful rollback means that the database connection works.
        self.errors_occurred = False
        self.needs_rollback = False
        self.run_on_commit = []

    # ### Backend-specific savepoint management methods ###

    def quote_name(self, name):
        if name.startswith('"') and name.endswith('"'):
            return name  # Quoting once is enough.
        return '"%s"' % name

    def _savepoint(self, sid):
        with self.cursor() as cursor:
            cursor.execute("SAVEPOINT %s" % self.quote_name(sid))

    def _savepoint_rollback(self, sid):
        with self.cursor() as cursor:
            cursor.execute("ROLLBACK TO SAVEPOINT %s" % self.quote_name(sid))

    def _savepoint_commit(self, sid):
        with self.cursor() as cursor:
            cursor.execute("RELEASE SAVEPOINT %s" % self.quote_name(sid))

    def _savepoint_allowed(self):
        # Savepoints cannot be created outside a transaction
        return self.uses_savepoints and not self.get_autocommit()

    # ### Generic savepoint management methods ###

    def savepoint(self):
        """
        Create a savepoint inside the current transaction. Return an
        identifier for the savepoint that will be used for the subsequent
        rollback or commit. Do nothing if savepoints are not supported.
        """
        if not self._savepoint_allowed():
            return

        thread_ident = _thread.get_ident()
        tid = str(thread_ident).replace("-", "")

        self.savepoint_state += 1
        sid = "s%s_x%d" % (tid, self.savepoint_state)

        self.validate_thread_sharing()
        self._savepoint(sid)

        return sid

    def savepoint_rollback(self, sid):
        """
        Roll back to a savepoint. Do nothing if savepoints are not supported.
        """
        if not self._savepoint_allowed():
            return

        self.validate_thread_sharing()
        self._savepoint_rollback(sid)

        # Remove any callbacks registered while this savepoint was active.
        self.run_on_commit = [
            (sids, func) for (sids, func) in self.run_on_commit if sid not in sids
        ]

    def savepoint_commit(self, sid):
        """
        Release a savepoint. Do nothing if savepoints are not supported.
        """
        if not self._savepoint_allowed():
            return

        self.validate_thread_sharing()
        self._savepoint_commit(sid)

    def clean_savepoints(self):
        """
        Reset the counter used to generate unique savepoint ids in this thread.
        """
        self.savepoint_state = 0

    # ##### Generic transaction management methods #####

    def _set_autocommit(self, autocommit):
        with self.wrap_database_errors:
            self.connection.autocommit = autocommit

    def get_autocommit(self):
        """Get the autocommit state."""
        self.ensure_connection()
        return self.autocommit

    def set_autocommit(
        self, autocommit, force_begin_transaction_with_broken_autocommit=False
    ):
        """
        Enable or disable autocommit.

        The usual way to start a transaction is to turn autocommit off.
        SQLite does not properly start a transaction when disabling
        autocommit. To avoid this buggy behavior and to actually enter a new
        transaction, an explicit BEGIN is required. Using
        force_begin_transaction_with_broken_autocommit=True will issue an
        explicit BEGIN with SQLite. This option will be ignored for other
        backends.
        """
        self.validate_no_atomic_block()
        self.ensure_connection()

        start_transaction_under_autocommit = (
            force_begin_transaction_with_broken_autocommit
            and not autocommit
            and hasattr(self, "_start_transaction_under_autocommit")
        )

        if start_transaction_under_autocommit:
            self._start_transaction_under_autocommit()
        else:
            self._set_autocommit(autocommit)

        self.autocommit = autocommit

        if autocommit and self.run_commit_hooks_on_set_autocommit_on:
            self.run_and_clear_commit_hooks()
            self.run_commit_hooks_on_set_autocommit_on = False

    def get_rollback(self):
        """Get the "needs rollback" flag -- for *advanced use* only."""
        if not self.in_atomic_block:
            raise TransactionManagementError(
                "The rollback flag doesn't work outside of an 'atomic' block."
            )
        return self.needs_rollback

    def set_rollback(self, rollback):
        """
        Set or unset the "needs rollback" flag -- for *advanced use* only.
        """
        if not self.in_atomic_block:
            raise TransactionManagementError(
                "The rollback flag doesn't work outside of an 'atomic' block."
            )
        self.needs_rollback = rollback

    def validate_no_atomic_block(self):
        """Raise an error if an atomic block is active."""
        if self.in_atomic_block:
            raise TransactionManagementError(
                "This is forbidden when an 'atomic' block is active."
            )

    def validate_no_broken_transaction(self):
        if self.needs_rollback:
            raise TransactionManagementError(
                "An error occurred in the current transaction. You can't "
                "execute queries until the end of the 'atomic' block."
            )

    # ### init method ###

    def concat_application_name(self, qs: str) -> str:
        if "application_name" not in qs:
            config_dict = self.config_dict
            application_name = config_dict.get("APPLICATION_NAME")
            if application_name is None:
                application_name = os.path.split(os.getcwd())[-1]
            return f"{qs} application_name={application_name}"
        return qs

    def get_connection_params(self) -> Dict:
        config_dict = self.config_dict
        # None may be used to connect to the default 'postgres' db
        dsn = config_dict.get("DSN")
        if dsn is None:
            raise ImproperlyConfigured("settings.DATABASE is improperly configured. ")
        if not re.match(r"(?P<key>\w+)=(?P<quote>[']?)(?P<value>.*?)(?P=quote)", dsn):
            raise ImproperlyConfigured(
                "DSN of setting.DATABASE is improperly configured, DSN: %s" % (dsn,)
            )
        conn_params = {
            "dsn": self.concat_application_name(dsn),
        }
        return conn_params

    def get_new_connection(self, connection_params) -> DatabaseConnection:
        connection = psycopg2.connect(**connection_params)

        # self.isolation_level must be set:
        # - after connecting to the database in order to obtain the database's
        #   default when no value is explicitly specified in options.
        # - before calling _set_autocommit() because if autocommit is on, that
        #   will set connection.isolation_level to ISOLATION_LEVEL_AUTOCOMMIT.
        try:
            self.isolation_level = self.config_dict["ISOLATION_LEVEL"]
        except KeyError:
            self.isolation_level = connection.isolation_level
        else:
            # Set the isolation level to the value from OPTIONS.
            if self.isolation_level != connection.isolation_level:
                connection.set_session(isolation_level=self.isolation_level)

        return connection
