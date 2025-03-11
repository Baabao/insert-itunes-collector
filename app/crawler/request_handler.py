import random
import ssl
import time
import traceback
from typing import List

import requests
import requests.adapters
import urllib3
from requests import HTTPError, RequestException

from app.crawler.exceptions import (
    CrawlerBlockException,
    CrawlerNotFoundException,
    CrawlerUnavailable,
)
from app.crawler.header import create_common_header, get_random_header
from log_helper.async_logger import get_async_logger

logger = get_async_logger(__name__)


def is_block_status(status: int) -> bool:
    return status in [403, 443]


def is_not_found_status(status: int) -> bool:
    return status in [404]


class HttpsAdapter1(requests.adapters.HTTPAdapter):
    """
    加入 ssl_context 用的 Adapter
    https://www.cnblogs.com/liuchaohao/p/14995526.html
    """

    def get_connection(self, *args, **kwargs):
        conn = super(HttpsAdapter1, self).get_connection(*args, **kwargs)
        if conn.conn_kw.get("ssl_context"):
            conn.conn_kw["ssl_context"].set_ciphers("DEFAULT:!DH")
        else:
            context = urllib3.util.ssl_.create_urllib3_context(ciphers="DEFAULT:!DH")
            conn.conn_kw["ssl_context"] = context
        return conn


class HttpsAdapter2(requests.adapters.HTTPAdapter):
    """
    加入 ssl_context 用的 Adapter
    https://stackoverflow.com/questions/61631955/python-requests-ssl-error-during-requests
    """

    def init_poolmanager(self, *args, **kwargs):
        ctx = ssl.create_default_context()
        ctx.set_ciphers("DEFAULT@SECLEVEL=1")
        kwargs["ssl_context"] = ctx
        return super(HttpsAdapter2, self).init_poolmanager(*args, **kwargs)


def get_random_adapters() -> List[type[requests.adapters.HTTPAdapter]]:
    adapter_list = [HttpsAdapter1, HttpsAdapter2]
    return random.sample(adapter_list, len(adapter_list))


def adapter_request(url: str) -> requests.Response:
    """
    使用 adapter 存取 rss (注意這裡是 SSL ON 的)
    """
    session_instance = requests.session()
    headers = get_random_header()
    adapters = get_random_adapters()

    for adapter in adapters:
        try:
            logger.info("try %s, url: %s", type(adapter).__name__, url)
            session_instance.mount("https://", adapter())
            return session_instance.get(url, headers=headers, verify=True)

        except HTTPError as exc:
            logger.info(
                "http error, url: %s, http code: %s", url, exc.response.status_code
            )

        except RequestException as exc:
            logger.info("requests error, url: %s, %s", url, exc)

        except Exception as exc:
            logger.info("unexpected error, url: %s, %s", url, exc)

    raise CrawlerUnavailable("all adapter are failed to request")


def safe_request(url: str, retry=False, wait_interval: int = 30) -> requests.Response:
    """
    Make a more safe request
    """
    try:
        headers = create_common_header()
        response = requests.get(url=url, headers=headers, verify=False)

        # do retry or not
        if retry and not response.ok:
            logger.info(
                "response is not okay, retry in %s seconds, http code: %s, url: %s",
                wait_interval,
                response.status_code,
                url,
            )
            time.sleep(30)
            response = requests.get(url=url, headers=headers, verify=False)
            logger.info(
                "requests has retried, http code: %s, url: %s",
                response.status_code,
                url,
            )

        if is_block_status(response.status_code):
            raise CrawlerBlockException()

        elif is_not_found_status(response.status_code):
            # since 2020.8, itunes api response 404 sometimes, raise NotFoundException for treating
            raise CrawlerNotFoundException()

        response.raise_for_status()
        return response

    except (CrawlerBlockException, ConnectionError) as exc:
        logger.info("requests blocked, %s", exc)
        raise CrawlerBlockException("Block error, %s" % (exc,)) from exc

    except CrawlerNotFoundException as exc:
        logger.info("requests not found, %s", exc)
        raise CrawlerNotFoundException("Not found error, %s" % (exc,)) from exc

    except (Exception,) as exc:
        logger.critical("unexpected error, %s", traceback.format_exc(10))
        raise CrawlerUnavailable("Unavailable error, %s" % (exc,)) from exc


def common_request(url: str) -> requests.Response:
    try:
        headers = create_common_header()
        response = requests.get(url=url, headers=headers, verify=False)
        logger.info("request_get_complete! %s", url)
        response.raise_for_status()
        return response

    except HTTPError as exc:
        logger.info(
            "http error, url: %s, http code: , %s", url, exc.response.status_code, exc
        )
        raise CrawlerUnavailable("Unavailable error, %s" % (exc,)) from exc

    except RequestException as exc:
        logger.info("requests error, url: %s, %s", url, exc)
        raise CrawlerUnavailable("Unavailable error, %s" % (exc,)) from exc

    except Exception as exc:
        logger.critical("unexpected error, url: %s, %s", url, exc)
        raise Exception("Unexpected error, %s" % (exc,)) from exc
