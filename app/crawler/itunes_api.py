from collections import namedtuple
from typing import Dict, Union

import requests

from app.crawler.request_handler import safe_request
from log_helper.async_logger import get_async_logger

logger = get_async_logger(__name__)

TopData = namedtuple("TopData", ["entry"])
LookupData = namedtuple("LookupData", ["resultCount", "results"])


def convert_resp_to_dict(resp: requests.Response) -> Dict:
    if not isinstance(resp, requests.Response):
        return {}
    return resp.json()


def create_itunes_genre_url(genre_id: int) -> str:
    return f"https://itunes.apple.com/tw/rss/toppodcasts/genre={str(genre_id)}/limit=200/json"


def create_itunes_lookup_url(collection_id: int) -> str:
    return f"https://itunes.apple.com/lookup?id={str(collection_id)}"


def create_itunes_search_url(keyword: str) -> str:
    return (
        f"https://itunes.apple.com/search?media=podcast&limit=200&term={str(keyword)}"
    )


def get_top_api_result(genre_id: Union[int, str], retry: bool = False) -> TopData:
    data = convert_resp_to_dict(
        safe_request(create_itunes_genre_url(int(genre_id)), retry)
    )
    return TopData(data.get("feed", {}).get("entry", []))


def get_lookup_api_result(
    collection_id: Union[int, str], retry: bool = False
) -> LookupData:
    data = convert_resp_to_dict(
        safe_request(create_itunes_lookup_url(int(collection_id)), retry)
    )
    return LookupData(resultCount=data["resultCount"], results=data["results"])


def get_search_api_result(term: Union[int, str], retry: bool = False) -> LookupData:
    data = convert_resp_to_dict(
        safe_request(create_itunes_search_url(str(term)), retry)
    )
    return LookupData(resultCount=data["resultCount"], results=data["results"])
