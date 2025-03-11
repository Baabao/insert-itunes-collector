import datetime
import traceback
from typing import Dict, List, Optional, Tuple

from app.collector.itunes_tag_handler import (
    create_tag_data,
    get_itunes_tag_data,
    get_update_date_field,
)
from app.common.collection import is_empty_list
from app.db.operations import get_tag_by_greater_created
from core.common.file_lock import FileLock, FileLockException
from core.common.fs_utils import FileHandleError, write_json
from log_helper.async_logger import get_async_logger

logger = get_async_logger(__name__)


def _is_tag_exist(tag_list: List) -> bool:
    return len(tag_list) > 0


def _get_diff_tag_list(
    new_tag_list: List[Dict], origin_tag_list: List[Dict]
) -> List[Dict]:
    origin_tag_id_list = [i.get("id") for i in origin_tag_list]
    return [tag for tag in new_tag_list if tag.get("id") not in origin_tag_id_list]


def _fetch_last_item_created_field(tag_list) -> Optional[datetime.datetime]:
    try:
        _, _, created = tag_list[-1]
        return created
    except IndexError:
        return None
    except Exception as exc:
        logger.critical("unexpected error, %s", exc)
        raise Exception("unexpected error, %s" % (exc,)) from exc


def _concat_new_tag_list(
    origin_tag_list: List[Dict], new_tag_list: List[Dict]
) -> List[Dict]:
    tag_list = origin_tag_list.copy()
    tag_list.extend(new_tag_list)
    return tag_list


def _integrate_tag_list(tag_list: List[Tuple]) -> List[Dict]:
    return [{"id": tag_id, "name": name} for tag_id, name, *_ in tag_list]


def _init_tag_data(itunes_tag_path: str) -> Dict:
    tag_data = get_itunes_tag_data(itunes_tag_path)
    tag_list = tag_data.get("tags", [])
    if is_empty_list(tag_list):
        update_date = get_update_date_field(tag_data)
        tag_data = create_tag_data(update_date=update_date, tag_list=[])
        write_json(fp=itunes_tag_path, data=tag_data)
    return tag_data


def sync_tag_data_from_db(itunes_tag_path: str) -> Dict:
    try:
        with FileLock(itunes_tag_path):
            tag_data = _init_tag_data(itunes_tag_path)

            update_date = get_update_date_field(tag_data)
            tag_list = tag_data.get("tags", [])

            from_db_tag_list = get_tag_by_greater_created(greater_date=update_date)

            if not _is_tag_exist(from_db_tag_list):
                return tag_data

            new_tag_list = _integrate_tag_list(from_db_tag_list)
            diff_tag_list = _get_diff_tag_list(new_tag_list, tag_list)
            if len(diff_tag_list) == 0:
                return tag_data

            merge_tag_list = _concat_new_tag_list(tag_list, diff_tag_list)
            new_update_date = _fetch_last_item_created_field(from_db_tag_list)
            if new_update_date is None:
                return create_tag_data(update_date=update_date, tag_list=merge_tag_list)

            new_tag_data = create_tag_data(
                update_date=new_update_date.strftime("%Y-%m-%d %H:%M:%S.%f%z"),
                tag_list=merge_tag_list,
            )

            write_json(fp=itunes_tag_path, data=new_tag_data)

            return new_tag_data

    except FileHandleError as exc:
        logger.error("file operator failed, %s", exc)
        return {}

    except FileLockException as exc:
        logger.error("lock failed, %s ", exc)
        return {}

    except Exception as exc:
        logger.critical(traceback.format_exc(10))
        raise Exception("unexpected error, %s" % (exc,)) from exc
