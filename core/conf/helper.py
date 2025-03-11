import os
from typing import Any

from core.utils.exceptions import ImproperlyConfigured


def get_env(key: str, default: Any = None, required: bool = True) -> Any:
    try:
        return os.environ[key]
    except KeyError as exc:
        if required:
            raise ImproperlyConfigured(
                f"You must define the environment variable {key}"
            ) from exc
        return default
