import abc
import json
import sys
from typing import Any, Dict, Optional

from core.utils.exceptions import ImproperlyConfigured

_LAYERS = {
    "app_config": {
        "name": "config",
        "instant": True,
        "require_keys": [
            "sql_lock_limit",
            "sql_lock_sleep_time",
            "sql_lock_insert_count",
            "sql_lock_update_count",
            "sql_lock_remove_count",
            "create_program_timeout",
            "fetch_rss_timeout",
            "insert_episode_timeout",
            "exclude_program_list_file_path",
        ],
    },
    "runner_config": {
        "name": "runner",
        "instant": True,
        "require_keys": [
            "continue_execute",
            "prepare_interval",
            "post_interval",
            "process_num",
        ],
    },
    "logging_config": {"name": "logger", "instant": False},
}

_REQUIRED_KEYS = [k for k, _ in _LAYERS.items()]
_DYNAMIC_KEYS = [v["name"] for _, v in _LAYERS.items()]


class BaseClass(object):
    def __init__(self, classtype) -> None:
        self._type = classtype

    def __getitem__(self, key: str) -> Any:
        """Allow dictionary-like access."""
        return getattr(self, key)


def cls_factory(name: str, attributes: Dict, base_cls=BaseClass):
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            if key not in attributes:
                raise TypeError(
                    f"Property attributes {key} not valid for {self.__class__.__name__}"
                )
            setattr(self, key, value)
        base_cls.__init__(self, name[: -len("Class")])

    new_class = type(name, (base_cls,), {"__init__": __init__})
    return new_class


class ExecutionInterface(abc.ABC):
    config: object
    runner: object
    logger: Dict


class Execution(ExecutionInterface):
    def __init__(self, json_path: str, dynamic: bool = False) -> None:
        self._json_path = json_path
        self.dynamic = dynamic
        self._config_data: Dict[str, Any] = {}
        self._load_config(json_path)

    def __getitem__(self, key: str) -> Any:
        """Allow dictionary-like access."""
        if key in _DYNAMIC_KEYS and self.dynamic:
            self.reload()
        return self._config_data[key]

    def __getattribute__(self, name: str) -> Any:
        if name in _DYNAMIC_KEYS and self.dynamic:
            self.reload()
        return super().__getattribute__(name)

    def __repr__(self) -> str:
        return f"Execution ({self._config_data})"

    def _load_config(self, json_path: str) -> None:
        try:
            with open(json_path, "r") as file:
                data = json.load(file)
            self._validate_config(data)
            self._config_data = data
            self._initial_config(data)

        except FileNotFoundError as exc:
            raise ImproperlyConfigured(
                f"Configuration file not found, json_path: {json_path}"
            ) from exc

        except json.JSONDecodeError as exc:
            raise ImproperlyConfigured(f"Invalid JSON, {exc}") from exc

    def _validate_config(self, config_data: Dict[str, Any]):
        for layer in _REQUIRED_KEYS:
            if layer not in config_data:
                raise ValueError(f"Missing required config key: {layer}")
            layer_config = _LAYERS.get(layer)
            if layer_config is None:
                continue
            instant = layer_config.get("instant")
            if not isinstance(instant, bool):
                raise ValueError(
                    f"Invalid value of instant field in configuration file, instant type: {type(instant)}"
                )
            if not instant:
                continue

            inner_config = config_data.get(layer, {})
            inner_keys = inner_config.keys()
            for key in layer_config.get("require_keys", []):
                if key not in inner_keys:
                    raise ValueError(f"Missing require {key} field of {layer} config")

    def reload(self, json_path: Optional[str] = None) -> None:
        """Reload the configuration from the given JSON file."""
        try:
            self._load_config(json_path or self._json_path)

        except ImproperlyConfigured as exc:
            sys.stderr.write(
                f"reload json configuration failure, {exc}\nusing previous json configuration.\n"
            )
            sys.stderr.flush()

        except Exception as exc:
            sys.stderr.write(
                f"unexpected error, {exc}\nusing previous json configuration.\n"
            )
            sys.stderr.flush()

    def _initial_config(self, data: Dict):
        _LAYERS.items()
        for key, attributes in data.items():
            if not isinstance(attributes, Dict):
                continue
            layer = _LAYERS.get(key)
            if layer is None:
                continue

            attr_name = layer.get("name")
            if not isinstance(attr_name, str):
                continue
            if layer.get("instant", False):
                cls = cls_factory(attr_name, attributes)
                attr_value = cls(**attributes)
            else:
                attr_value = attributes
            setattr(self, attr_name, attr_value)
