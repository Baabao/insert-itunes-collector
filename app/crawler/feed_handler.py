import os
import re
import traceback
from typing import Optional, Union

import feedparser
import requests
import requests.adapters
import urllib3
from feedparser import FeedParserDict
from requests import RequestException
from requests.exceptions import HTTPError

from app.crawler.exceptions import FeedException
from app.crawler.header import create_common_header
from app.crawler.request_handler import adapter_request
from config.constants import FEED_DATA_PATH
from core.common.fs_utils import write_xml_with_et
from log_helper.async_logger import get_async_logger

urllib3.disable_warnings()

logger = get_async_logger(__name__)


def is_ic_975_url(url: str) -> bool:
    return "ic975.com" in url


def create_feed_data_fp(fp: str, collection_id: Union[str, int]) -> str:
    return os.path.join(fp, f"{str(collection_id)}.xml")


def feeder_work(url) -> FeedParserDict:
    try:
        request_headers = create_common_header()
        result = feedparser.parse(
            url,
            response_headers={"content-type": "text/xml; charset=utf-8"},
            request_headers=request_headers,
        )
        return result
    except Exception as exc:
        logger.info("request feed failed, url: %s, %s", url, exc)
        raise FeedException from exc


def feeder_work_and_save(url, collection_id) -> Optional[FeedParserDict]:
    feed_data_path = FEED_DATA_PATH

    feed_data_fp = create_feed_data_fp(feed_data_path, collection_id)

    try:
        # 1. request
        if is_ic_975_url(url):
            # 若為 ic975，優先使用 adapter 去 call (只是不想再製造多一次的 503 response ，免得多留不正確的黑紀錄)
            response = adapter_request(url=url)
        else:
            headers = create_common_header()
            response = requests.get(url=url, headers=headers, verify=False)
            # 若有其他的 503，試試看 adapter 去 call
            if response and response.status_code == "503":
                logger.info("response http status 503, url: %s", url)
                response = adapter_request(url=url)

        response.raise_for_status()

        # 2. save xml
        try:
            write_xml_with_et(feed_data_fp, response.content)
        except Exception as exc:
            logger.info(
                "save XML failed, collection_id: %s, url: %s, %s",
                collection_id,
                url,
                exc,
            )

        # 3. parse by feedparser
        result = feedparser.parse(
            response.content,
            response_headers={"content-type": "text/xml; charset=utf-8"},
        )

        # 4. retry if bozo occur
        if result.get("bozo") != 0:
            # 4.1 response has bozo - means XML not well-fromed
            feed_encoding = result.get("encoding", None)
            bozo_message = result.get("bozo_exception", "bozo error")
            logger.info(
                "bozo error, collection_id: %s, encoding: %s, bozo_exception: %s, will try filter C0",
                collection_id,
                bozo_message,
                feed_encoding,
            )

            if not feed_encoding:
                logger.info(
                    "feedparser get encoding empty, collection_id: %s, try utf-8",
                    collection_id,
                )
                feed_encoding = "utf-8"

            # 4.1.1 filter C0 except x09, x0D, x0A
            #  [\u0000-\u001F\u007F] (all C0, cntrl: https://www.regular-expressions.info/posixbrackets.html)
            #  [\u0000-\u0008\u000B\u000C\u000E-\u001F\u007F] (C0 except x09, x0D, x0A, https://regex101.com/r/36zomv/6)
            response_str = response.content.decode(feed_encoding)
            response_str = re.sub(
                r"[\u0000-\u0008\u000B\u000C\u000E-\u001F\u007F]", "", response_str
            )

            # 4.1.2 save again
            try:
                write_xml_with_et(feed_data_fp, response.content)
            except Exception as exc:
                logger.info(
                    "save XML failed again, collection_id: %s, url: %s, %s",
                    collection_id,
                    url,
                    exc,
                )

            # 4.1.3 parse again
            result = feedparser.parse(
                response_str,
                response_headers={"content-type": "text/xml; charset=utf-8"},
            )
            if result.get("bozo") == 0:
                logger.info(
                    "feedparser retry success, collection_id: %s", collection_id
                )

        if result.get("bozo") != 0:
            # 4.2 still has bozo
            feed_encoding2 = result.get("encoding", None)
            bozo_message2 = result.get("bozo_exception", "bozo error")
            # record log for observation
            logger.info(
                "bozo error again, collection_id: %s, encoding: %s, bozo_exception: %s",
                collection_id,
                bozo_message2,
                feed_encoding2,
            )

        return result

    except (HTTPError, RequestException) as exc:
        logger.info("request or response error, url: %s, %s", url, exc)
        return None

    except Exception as exc:
        logger.critical("unexpected error, url: %s, %s", url, traceback.format_exc(10))
        raise FeedException from exc
