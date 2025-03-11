import pickle
from multiprocessing.managers import BaseProxy
from typing import Any


def is_int(value):
    """Check if the value is an integer."""
    return isinstance(value, int)


def is_float(value):
    """Check if the value is a float."""
    return isinstance(value, float)


def is_str(value):
    """Check if the value is a string."""
    return isinstance(value, str)


def is_bool(value):
    """Check if the value is a boolean."""
    return isinstance(value, bool)


def is_list(value):
    """Check if the value is a list."""
    return isinstance(value, list)


def is_tuple(value):
    """Check if the value is a tuple."""
    return isinstance(value, tuple)


def is_dict(value):
    """Check if the value is a dictionary."""
    return isinstance(value, dict)


def is_set(value):
    """Check if the value is a set."""
    return isinstance(value, set)


def is_picklable(obj):
    try:
        pickle.dumps(obj)  # Try to pickle the object
        return True
    except (pickle.PickleError, TypeError, AttributeError):
        return False  # Object is not picklable


def is_unpicklable(pickled_obj):
    try:
        pickle.loads(pickled_obj)  # Try to unpickle
        return True
    except (pickle.PickleError, TypeError, AttributeError, EOFError):
        return False  # Not unpicklable


def is_processing_proxy(value: Any) -> bool:
    return isinstance(value, BaseProxy)
