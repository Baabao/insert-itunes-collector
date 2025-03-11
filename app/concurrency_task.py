import timeit
from multiprocessing import BoundedSemaphore
from threading import Thread
from typing import Dict

from app.common.inspect import diff_time
from app.crawler import crawl_detail, crawl_top
from app.crawler.exceptions import CrawlerUnavailable
from log_helper.async_logger import get_async_logger

logger = get_async_logger(__name__)


def get_detail(collection_dict, retry_dict, collection_id) -> None:
    """
    Get Lookup Detail for Insert Schedule
        (1) call lookup api
        (2) save result into Dict collection_dict
        (3) add into retry if meet BlockException or NotFoundException
    """
    try:
        logger.info("%s start", collection_id)

        detail = next(
            (
                value
                for key, value in list(collection_dict.items())
                if collection_id == key
            ),
            None,
        )

        if not detail:
            logger.info("%s run", collection_id)
            detail = crawl_detail(collection_id=collection_id)
            collection_dict.update({collection_id: detail})

        logger.info("%s end", collection_id)

    except CrawlerUnavailable as exc:
        # do retry when both block & not found
        exception_name = exc.__class__.__name__
        logger.info("[%s] %s start (%s)", exception_name, collection_id, str(exc))

        count = retry_dict.get(collection_id)

        if count is None:
            # New one, has 3 times quota
            logger.info("[%s] count_zero! %s", exception_name, collection_id)

            retry_dict.update({collection_id: 3})

        elif count < 1:
            # latest one
            logger.info("[%s] %s remove with loop limit", exception_name, collection_id)

        else:
            # Minus quota count
            logger.info("[%s] update_count %s", exception_name, collection_id)

            retry_dict.update({collection_id: (count - 1)})

        logger.info("[%s] %s end", exception_name, collection_id)

    except Exception as exc:
        logger.error("unexpected error, %s", exc)


def get_top(collection_dict, retry_dict, cost_list, collection_list, genre_id) -> Dict:
    """
    Call Top Api, then call lookup api for every collection
    """
    top_list = []
    try:
        top_list = crawl_top(genre_id)

        sem_lock = BoundedSemaphore(10)
        for collection_id in top_list:
            if collection_id in collection_list:
                continue

            start_time = timeit.default_timer()
            get_detail(collection_dict, retry_dict, collection_id)

            sem_lock.acquire()

            t = Thread(
                target=get_detail, args=(collection_dict, retry_dict, collection_id)
            )
            t.start()
            t.join()

            sem_lock.release()

            cost_list.append({"genre_id": genre_id, "cost_time": diff_time(start_time)})

    # for crawl top error: BlockException or NotFoundException
    except CrawlerUnavailable as e:
        logger.info("[get_top][insert][%s] genre %s", e.__class__.__name__, genre_id)

    except Exception as e:
        logger.info("[get_top][insert][Error] %s %s", genre_id, str(e))

    finally:
        return {genre_id: top_list}
