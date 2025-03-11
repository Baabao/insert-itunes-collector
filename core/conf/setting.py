import importlib
import os
from typing import Dict

from core.conf import globe_setting
from core.utils.exceptions import ImproperlyConfigured
from core.utils.lazy import LazyObject, empty

PROD_ENVIRONMENT = "PROD"
VALID_SETTINGS = ("local", "test", "staging", "prod")


class Settings:
    def __init__(self, settings_module):
        self.setting_module = settings_module

        for base_key in dir(globe_setting):
            if not self._is_definitive_setting(base_key):
                continue
            setattr(self, base_key, getattr(globe_setting, base_key))

        mod = importlib.import_module(self.setting_module)

        self._explicit_settings = set()

        for mod_key in dir(mod):
            if not self._is_definitive_setting(mod_key):
                continue
            attr_val = getattr(self, mod_key, None)
            mod_val = getattr(mod, mod_key, None)
            if isinstance(attr_val, dict) and isinstance(mod_val, dict):
                mod_val = self._recursive_update(attr_val, mod_val)
            setattr(self, mod_key, mod_val)
            self._explicit_settings.add(mod_key)

    def _is_definitive_setting(self, key: str) -> bool:
        if key.startswith("_") or key.endswith("_"):
            return False
        if not key.isupper():
            return False
        return True

    def _recursive_update(self, a_dict: Dict, b_dict: Dict) -> Dict:
        new_dict = a_dict.copy()
        for key in a_dict.keys() | b_dict.keys():
            a_val = a_dict.get(key)
            b_val = b_dict.get(key)
            if isinstance(a_val, dict) and isinstance(b_val, dict):
                new_dict.update({key: self._recursive_update(a_val, b_val)})
            elif a_val and b_val:
                new_dict.update({key: b_val})
            elif a_val is None:
                new_dict.update({key: b_val})
        return new_dict


CACHE = {
    "ENDPOINT_URL": "127.0.0.1",
    "DB": {
        # number must map real redis db
        0: {"NAME": "django", "PREFIX": ""},
        1: {"NAME": "insert_itunes_collector", "PREFIX": "insert_itunes_collector"},
    },
}


CACHE_B = {
    "ENDPOINT_URL": "127.0.0.1",
    "DB": {
        # number must map real redis db
        0: {"NAME": "django", "PREFIX": ""},
        1: {"NAME": "insert_itunes_collector", "PREFIX": "insert_itunes_collector"},
    },
}


class LazySetting(LazyObject):
    _wrapped = None

    def _setup(self):
        prod = os.environ.get(PROD_ENVIRONMENT)

        if not prod:
            raise ImproperlyConfigured(
                "Settings are not configured. "
                f"You must either define the environment variable {PROD_ENVIRONMENT}."
            )

        if prod not in VALID_SETTINGS:
            raise ImproperlyConfigured(f"Not support environment. ({prod})")

        settings_module = f"settings.{prod}"
        self._wrapped = Settings(settings_module)

    def __getattr__(self, name):
        if self._wrapped is empty:
            self._setup()
        val = getattr(self._wrapped, name)
        self.__dict__[name] = val
        return val

    def __setattr__(self, name, value):
        """
        Set the value of setting. Clear all cached values if _wrapped changes
        (@override_settings does this) or clear single values when set.
        """
        if name == "_wrapped":
            self.__dict__.clear()
        else:
            self.__dict__.pop(name, None)

        if self._wrapped is not None:
            val = self.__getattribute__(name)
            if isinstance(value, dict) and isinstance(val, dict):
                value = {**val, **value}

        super().__setattr__(name, value)
