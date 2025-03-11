class ImproperlyConfigured(Exception):
    """Improperly configured"""

    pass


class FileHandleError(Exception):
    """fs_utils.py utility error"""

    pass


class SynchronousOnlyOperation(Exception):
    """The user tried to call a sync-only function from an async context."""

    pass
