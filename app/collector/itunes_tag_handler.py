import os
import traceback
from json import JSONDecodeError
from typing import Dict, List

from core.common.file_lock import FileLock, FileLockException
from core.common.fs_utils import FileHandleError, read_json, write_json
from core.common.string import to_utf8_string
from log_helper.async_logger import get_async_logger

logger = get_async_logger(__name__)

__tags_json_format = {
    "update_date": "2025-01-01 00:00:00.000000+00",
    "tags": [{"name": "ABC"}],
}


def concat_tag_path(path: str) -> str:
    return f"{path}/tags.json"


def create_tag_item(tag_id: int, tag_name: str) -> Dict:
    return {"id": tag_id, "name": tag_name}


def create_tag_data(update_date: str, tag_list: List[Dict]) -> Dict:
    return {"update_date": update_date, "tags": tag_list}


def get_update_date_field(tag_data: Dict) -> str:
    return tag_data.get("update_date", "2016-01-01 00:00:00.000000+08")


def get_itunes_tag_data(itunes_tag_fp: str) -> Dict:
    try:
        if os.path.exists(itunes_tag_fp):
            return read_json(itunes_tag_fp)
        return {}

    except (FileHandleError, JSONDecodeError) as exc:
        logger.error("file operator failed, %s", exc)
        return {}

    except Exception as exc:
        logger.critical(traceback.format_exc(10))
        raise Exception("Unexpected error, %s" % (exc,)) from exc


def find_itunes_tag(itunes_tag_fp: str, tag_name: str) -> Dict:
    try:
        fixed_tag_name = to_utf8_string(tag_name)
        tag_data = get_itunes_tag_data(itunes_tag_fp)
        return next(
            (
                tag
                for tag in tag_data.get("tags", [])
                if to_utf8_string(tag.get("name")) == fixed_tag_name
            ),
            {},
        )

    except FileHandleError as exc:
        logger.error("file operator failed, %s", exc)
        return {}

    except Exception as exc:
        logger.critical(traceback.format_exc(10))
        raise Exception("unexpected error, %s" % (exc,)) from exc


def update_itunes_tag_data(itunes_tag_fp: str, tags: List[Dict]) -> None:
    try:
        if not tags:
            return

        data = read_json(itunes_tag_fp)
        if not data:
            return

        with FileLock(itunes_tag_fp):
            created_time = data.get("update_date")
            original_tags = data.get("tags", [])

            original_tag_ids = [tag.get("id") for tag in original_tags]

            new_tags = []
            for tag in tags:
                if tag.get("id") not in original_tag_ids:
                    new_tags.append(tag)

            if new_tags:
                original_tags.extend(new_tags)
                new_tag_data = create_tag_data(created_time, original_tags)

                write_json(itunes_tag_fp, new_tag_data)

    except FileHandleError as exc:
        logger.error("file operator failed, %s", exc)

    except FileLockException as exc:
        logger.error("lock failed, %s ", exc)

    except Exception as exc:
        logger.critical(traceback.format_exc(10))
        raise Exception("unexpected error, %s" % (exc,)) from exc
