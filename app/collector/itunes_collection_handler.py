from typing import Any, Dict, List, Union

from app.common.exceptions import ItunesDataFieldNotFoundError
from core.common.fs_utils import FileHandleError, remove_file, write_json
from core.common.string import to_utf8_string, trim_string
from log_helper.async_logger import get_async_logger

logger = get_async_logger(__name__)


def concat_collection_file(directory_path: str, collection_id: Union[int, str]) -> str:
    return f"{directory_path}/{collection_id}.json"


def concat_collection_backup_file(
    directory_path: str, collection_id: Union[int, str]
) -> str:
    return f"{directory_path}/{collection_id}.json.bak"


def write_itunes_data(
    itunes_collection_path: str, collection_id: Union[int, str], data: Union[List, Dict]
) -> None:
    itunes_collection_fp = concat_collection_file(itunes_collection_path, collection_id)

    try:
        write_json(itunes_collection_fp, data)

    except FileHandleError as exc:
        logger.error(
            "file operator failed, itunes_collection_path: %s, collection_id: %s, file error: %s",
            itunes_collection_fp,
            collection_id,
            exc,
        )
        raise FileHandleError("File operator failed, %s" % (exc,)) from exc
    except Exception as exc:
        logger.critical(
            "remove failed, itunes_collection_path: %s, collection_id: %s, error: %s",
            itunes_collection_fp,
            collection_id,
            exc,
        )
        raise Exception("Unexpected error, %s" % (exc,)) from exc


def remove_itunes_data(
    itunes_collection_path: str, collection_id: Union[int, str]
) -> None:
    itunes_collection_fp = concat_collection_file(itunes_collection_path, collection_id)
    itunes_collection_bak_fp = concat_collection_backup_file(
        itunes_collection_path, collection_id
    )

    try:
        remove_file(itunes_collection_fp)
        remove_file(itunes_collection_bak_fp)

    except FileHandleError as exc:
        logger.error(
            "file operator failed, itunes_collection_path: %s, collection_id: %s, file error: %s",
            itunes_collection_fp,
            collection_id,
            exc,
        )
        raise FileHandleError("File operator failed, %s" % (exc,)) from exc
    except Exception as exc:
        logger.critical(
            "unexpected error, itunes_collection_path: %s, collection_id: %s, error: %s",
            itunes_collection_fp,
            collection_id,
            exc,
        )
        raise Exception("Unexpected error, %s" % (exc,)) from exc


def _get_data_property(data: Dict, key: str) -> Any:
    value = data.get(key)
    if value is None:
        raise ItunesDataFieldNotFoundError("field %s not found" % (key,))
    return value


def get_collection_name(data: Dict) -> str:
    return trim_string(to_utf8_string(_get_data_property(data, "collectionName")))


def get_artwork_url_600(data: Dict) -> str:
    return trim_string(to_utf8_string(_get_data_property(data, "artworkUrl600")))


def get_feed_url(data: Dict) -> str:
    return _get_data_property(data, "feedUrl")


def get_genre_ids(data: Dict) -> List:
    return data.get("genreIds", [])


def create_itunes_data(
    feed_url: str,
    title: str,
    image_url: str,
    episode_list: List,
    genre_id_list: List,
    genre_name_list: List,
) -> Dict:
    return {
        "has_rss": True,
        "has_data": True,
        "feed_url": feed_url,
        "program_title": title,
        "program_description": "",
        "program_img_url": image_url,
        "has_episode": any(episode_list),
        "episodes": episode_list,
        "genre_ids": genre_id_list,
        "genres": genre_name_list,
    }
