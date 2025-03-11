import multiprocessing
import traceback
from typing import Any, Dict, Optional

import urllib3

from app.crawler.exceptions import CrawlerBlockException, CrawlerNotFoundException
from app.crawler.feed_handler import feeder_work, feeder_work_and_save
from app.crawler.itunes_api import (
    get_lookup_api_result,
    get_search_api_result,
    get_top_api_result,
)
from app.crawler.wrapper import abort_wrapper
from log_helper.async_logger import get_async_logger

urllib3.disable_warnings()

logger = get_async_logger(__name__)


def get_collection_id(data):
    collection_id = None
    id_data = data.get("id")
    if id_data:
        attributes_data = id_data.get("attributes")
        if attributes_data:
            collection_id = attributes_data.get("im:id")
    return collection_id


def crawl_top(genre_id: int):
    try:
        rank_data = []
        top_data = get_top_api_result(genre_id)

        for entry in top_data.entry:
            collection_id = get_collection_id(data=entry)
            if collection_id:
                rank_data.append(collection_id)

        return rank_data

    except Exception as exc:
        logger.info("unexpected error, %s", exc)
        raise exc


def crawl_detail(collection_id) -> Dict:
    try:
        lookup_data = get_lookup_api_result(collection_id=collection_id)

        # return empty result for this case, collection will delete due to no feedUrl data
        if lookup_data.resultCount == 0 and len(lookup_data.results) == 0:
            logger.info(
                "empty result, collection_id: %s, result: %s",
                collection_id,
                lookup_data,
            )
            return {}

        result = lookup_data.results[0]
        return result

    except IndexError as exc:
        raise Exception(
            "Zero result for collection id %s: %s" % (collection_id, str(exc))
        )

    except CrawlerBlockException as exc:
        raise CrawlerBlockException(
            "Block error for collection id %s: %s" % (collection_id, str(exc))
        )

    except CrawlerNotFoundException as exc:
        raise CrawlerNotFoundException(
            "Not Found error for collection id %s: %s" % (collection_id, str(exc))
        )

    except Exception as exc:
        raise Exception(
            "Occur error about collection id %s: %s" % (collection_id, str(exc))
        )


def crawl_detail_for_update_daemon(collection_id) -> Dict:
    """
    Porting from crawl_detail, call lookup api and treate its response
        - return data format different
    """
    try:
        lookup_data = get_lookup_api_result(collection_id=collection_id)

        # return empty result for this case, collection will be deleting due to no feedUrl data
        if lookup_data.resultCount == 0 and len(lookup_data.results) == 0:
            # means collection OFF in apple podcast
            logger.info(
                "empty result, collection_id: %s, result: %s",
                collection_id,
                lookup_data,
            )
            return {"itunes_program_status": "deletable"}

        result = lookup_data.results[0]
        return result

    except IndexError as exc:
        raise Exception(
            "Zero result for collection id %s: %s" % (collection_id, str(exc))
        )

    except CrawlerBlockException as exc:
        raise CrawlerBlockException(
            "Block error for collection id %s: %s" % (collection_id, str(exc))
        )

    except CrawlerNotFoundException as exc:
        raise CrawlerNotFoundException(
            "Not Found error for collection id %s: %s" % (collection_id, str(exc))
        )

    except Exception as exc:
        raise Exception(
            "Occur error about collection id %s: %s" % (collection_id, str(exc))
        )


def crawl_detail_by_search(term, wait_and_retry=False) -> Dict:
    """
    Call Search Api
    """
    try:
        lookup_data = get_search_api_result(term=term, retry=wait_and_retry)

        for result in lookup_data.results or []:
            if result.get("collectionName") == term:
                return result

        logger.info("No Collection match the input term: %s", term)
        logger.info("FYI - Search Results: %s", lookup_data.results)
        raise IndexError

    except IndexError as exc:
        raise Exception("Zero result for term %s: %s" % (term, str(exc)))

    except CrawlerBlockException as exc:
        raise CrawlerBlockException("Block error for term %s: %s" % (term, str(exc)))

    except CrawlerNotFoundException as exc:
        raise CrawlerNotFoundException(
            "Not Found error for term %s: %s" % (term, str(exc))
        )

    except Exception as exc:
        raise Exception("Occur error about term %s: %s" % (term, str(exc)))


def crawl_feeder(url: str, timeout=10) -> Optional[Any]:
    result = None

    try:
        result = abort_wrapper(feeder_work, url, timeout=timeout)

    except multiprocessing.TimeoutError as exc:
        logger.info("feeder_work timeout error, url: %s, %s", url, exc)

    except Exception as _:
        logger.info(
            "feeder_work get unexpected error, url: %s, %s",
            url,
            traceback.format_exc(10),
        )

    if result is None:
        logger.info("feeder_work get nothing")
    else:
        if result.get("bozo") != 0:
            logger.info(
                "feeder_work bozo error, bozo_exception: %s",
                result.get("bozo_exception", "bozo error"),
            )

        if result.get("status", 404) not in [200, 302, 301]:
            logger.info(
                "feeder_work http status error, status: %s", result.get("status")
            )

    return result


def crawl_feeder_and_save(url, collection_id, timeout=10):
    result = None

    try:
        result = abort_wrapper(
            feeder_work_and_save, url, collection_id, timeout=timeout
        )

    except multiprocessing.TimeoutError as exc:
        logger.info("feeder_work timeout error, url: %s, %s", url, exc)

    except Exception as _:
        logger.info(
            "feeder_work get unexpected error, url: %s, %s",
            url,
            traceback.format_exc(10),
        )

    if result is None:
        logger.info("feeder_work get nothing")

    else:
        if result.get("bozo") != 0:
            logger.info(
                "feeder_work bozo error, bozo_exception: %s",
                result.get("bozo_exception", "bozo error"),
            )

    return result
