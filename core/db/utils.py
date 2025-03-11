"""
refer: https://peps.python.org/pep-0249/

Structure:
    Exception (built-in)
    |__Warning
    |__Error
       |__InterfaceError
       |__DatabaseError
          |__DataError
          |__OperationalError
          |__IntegrityError
          |__InternalError
          |__ProgrammingError
          |__NotSupportedError
"""


class Error(Exception):
    """
    Exception that is the base class of all other error exceptions. You can use this to catch all errors with one
    single except statement.
    """

    pass


class InterfaceError(Error):
    """
    Exception raised for errors that are related to the database interface rather than the database itself.
    """

    pass


class DatabaseError(Error):
    """
    Exception raised for errors that are related to the database.
    """

    pass


class DataError(DatabaseError):
    """
    Exception raised for errors that are due to problems with the processed data like division by zero, numeric value
    out of range, etc.
    """

    pass


class OperationalError(DatabaseError):
    """
    Exception raised for errors that are related to the database’s operation and not necessarily under the control of
    the programmer, e.g. an unexpected disconnect occurs, the data source name is not found, a transaction could not
    be processed, a memory allocation error occurred during processing, etc.
    """

    pass


class IntegrityError(DatabaseError):
    """
    Exception raised when the relational integrity of the database is affected, e.g. a foreign key check fails.
    """

    pass


class InternalError(DatabaseError):
    """
    Exception raised when the database encounters an internal error, e.g. the cursor is not valid anymore,
    the transaction is out of sync, etc.
    """

    pass


class ProgrammingError(DatabaseError):
    """
    Exception raised for programming errors, e.g. table not found or already exists, syntax error in the SQL statement,
    wrong number of parameters specified, etc.
    """

    pass


class NotSupportedError(DatabaseError):
    """
    Exception raised in case a method or database API was used which is not supported by the database,
    e.g. requesting a .rollback() on a connection that does not support transaction or has transactions turned off.
    """

    pass


class DatabaseErrorWrapper:
    """
    Context manager and decorator that reraises backend-specific database
    exceptions using Django's common wrappers.
    """

    def __init__(self, wrapper):
        """
        wrapper is a database wrapper.

        It must have a Database attribute defining PEP-249 exceptions.
        """
        self.wrapper = wrapper

    def __enter__(self):
        pass

    def __exit__(self, exc_type, exc_value, traceback):
        if exc_type is None:
            return
        for exc_type in (
            DataError,
            OperationalError,
            IntegrityError,
            InternalError,
            ProgrammingError,
            NotSupportedError,
            DatabaseError,
            InterfaceError,
            Error,
        ):
            db_exc_type = getattr(self.wrapper.Database, exc_type.__name__)
            if issubclass(exc_type, db_exc_type):
                exc_value = exc_type(*exc_value.args)
                # Only set the 'errors_occurred' flag for errors that may make
                # the connection unusable.
                if exc_type not in (DataError, IntegrityError):
                    self.wrapper.errors_occurred = True
                raise exc_value.with_traceback(traceback) from exc_value

    def __call__(self, func):
        # Note that we are intentionally not using @wraps here for performance
        # reasons. Refs #21109.
        def inner(*args, **kwargs):
            with self:
                return func(*args, **kwargs)

        return inner
