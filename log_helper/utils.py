import os
from typing import Any, Dict

from config.constants import PROJECT_PATH


def resolve_file_path(config_dict: Dict) -> Dict:
    handlers = config_dict.get("handlers", {})
    for name, value in handlers.items():
        detail = handlers[name]
        file_path = value.get("filename")
        if file_path:
            detail["filename"] = os.path.join(PROJECT_PATH, file_path)
    return config_dict


def dir_attrs(obj: Any) -> str:
    try:
        if isinstance(obj, dict):
            return str(dict(obj))
        properties = {
            attr: getattr(obj, attr)
            for attr in dir(obj)
            if not attr.startswith("__") and not callable(getattr(obj, attr))
        }
        return str(properties)
    except Exception:
        pass
    return repr(obj)
