# type: ignore
import json
import os
import shutil
import time
from copy import copy
from typing import AnyStr, Dict, List, Union

from core.common.string import is_byte_string
from core.utils.exceptions import FileHandleError

try:
    import xml.etree.cElementTree as ET
except ImportError:
    import xml.etree.ElementTree as ET


def read_file(fp: str) -> str:
    with open(fp, "r", encoding="utf-8") as file:
        return file.read()


def write_file(fp: str, data: AnyStr, mode: str = "w") -> AnyStr:
    copy_data = copy(data)
    encoding = None if is_byte_string(data) else "utf-8"
    with open(fp, mode, encoding=encoding) as file:
        file.write(copy_data)
    return copy_data


def remove_file(fp: str) -> bool:
    try:
        if os.path.exists(fp):
            os.remove(fp)
            time.sleep(0.1)
            return True
        return False
    except Exception as exc:
        raise FileHandleError(f"unexpected error, {exc}") from exc


def backup_file(fp: str) -> None:
    try:
        shutil.copy(fp, f"{fp}.bak")
        time.sleep(0.1)
    except Exception as exc:
        raise FileHandleError(f"unexpected error, {exc}") from exc


def restore_file(fp: str) -> None:
    try:
        if os.path.exists(f"{fp}.bak"):
            shutil.move(f"{fp}.bak", fp)
            time.sleep(0.1)
    except Exception as exc:
        raise FileHandleError(f"unexpected error, {exc}") from exc


def read_json(fp: str) -> Union[Dict, List]:
    with open(fp, "r", encoding="utf-8") as file:
        return json.load(file)


def write_json(fp: str, data: Union[List, Dict]) -> None:
    try:
        with open(fp, "w+", encoding="utf-8") as file:
            file.write(json.dumps(data, ensure_ascii=False))
        time.sleep(0.1)

    except Exception as exc:
        raise FileHandleError("unexpected error, %s" % (exc,)) from exc


def write_xml_with_et(fp: str, string: AnyStr) -> None:
    try:
        root = ET.fromstring(string)
        tree = ET.ElementTree(root)
        tree.write(fp)
    except Exception as exc:
        raise FileHandleError(f"unexpected error, {exc}") from exc
