class ImproperlyConfigured(Exception):
    """Improperly configured"""


class FileHandleError(Exception):
    """fs_utils.py utility error"""


class SynchronousOnlyOperation(Exception):
    """The user tried to call a sync-only function from an async context."""
