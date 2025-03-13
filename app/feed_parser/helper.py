from typing import Any, Callable, Dict, List, Optional, Union

from feedparser import FeedParserDict

from app.common.collection import (
    apply_method_with_list_to_get_all_result,
    apply_methods_to_get_all_result,
    apply_methods_to_get_first_match_result,
    find_item_with_key,
)
from app.common.exceptions import (
    FeedResultException,
    FeedResultFieldNotFoundError,
    FeedResultTypeError,
    FormatterException,
)
from app.feed_parser.field_method import (
    fetch_author_detail_key_method,
    fetch_author_key_method,
    fetch_authors_key_method,
    fetch_content_method,
    fetch_description_method,
    fetch_enclosures_method,
    fetch_image_href_method,
    fetch_itunes_duration_method,
    fetch_pub_date_method,
    fetch_published_method,
    fetch_subtitle_method,
    fetch_summary_method,
    fetch_tags_method,
    fetch_term_method,
)
from app.feed_parser.formatter import (
    basic_datetime_formatter,
    duration_formatter,
    fix_short_month_datetime_formatter,
    fix_week_alias_datetime_formatter,
    has_string,
    html_to_string_formatter,
    remove_html_tag_formatter,
    string_formatter,
)
from core.common.string import (
    is_audio_url,
    is_email,
    is_url_string,
    trim_string,
    try_fixing_url,
)
from log_helper.async_logger import get_async_logger
from log_helper.utils import dir_attrs

logger = get_async_logger(__name__)


def is_good_feed_dict(feed_dict: FeedParserDict) -> bool:
    if feed_dict is None:
        return False
    if not isinstance(feed_dict, FeedParserDict):
        raise TypeError(f"Incorrect type, feed_field: {type(feed_dict)}")
    if get_feed_field(feed_dict) is None:
        raise FeedResultFieldNotFoundError(
            f"Field feed not found, {dir_attrs(feed_dict)}"
        )
    if get_feed_entries_field(feed_dict) is None:
        raise FeedResultFieldNotFoundError(
            f"Field entries not found, {dir_attrs(feed_dict)}"
        )
    return True


def get_feed_field(feed_dict: FeedParserDict) -> Optional[Dict]:
    return feed_dict.get("feed")


def get_feed_entries_field(feed_dict: FeedParserDict) -> List:
    return feed_dict.get("entries", [])


def get_feed_img_url(feed_field: Dict) -> str:
    href = fetch_image_href_method(feed_field)
    img_url = string_formatter(href)
    if not is_url_string(img_url):
        img_url = try_fixing_url(img_url)
    return img_url


def _fetch_author_key_wrapper(
    possible_methods: List[Callable], feed_dict: Dict, key: str
) -> Any:
    field = apply_methods_to_get_first_match_result(possible_methods, feed_dict, key)
    if field is None:
        raise FeedResultFieldNotFoundError(
            f"Field {key} not found, {dir_attrs(feed_dict)}"
        )
    return field


def get_feed_author_name_field(feed_field: Dict) -> str:
    possible_methods = [
        fetch_author_detail_key_method,
        fetch_authors_key_method,
        fetch_author_key_method,
    ]
    name = _fetch_author_key_wrapper(possible_methods, feed_field, "name")
    return string_formatter(name)


def get_feed_author_email_field(feed_field: Dict) -> str:
    possible_methods = [
        fetch_author_detail_key_method,
        fetch_authors_key_method,
        fetch_author_key_method,
    ]
    email = _fetch_author_key_wrapper(possible_methods, feed_field, "email")
    if not is_email(email):
        raise FeedResultFieldNotFoundError(
            f"Field email is not a correct email string, email: {email}"
        )
    return string_formatter(email)


def get_feed_data_uri_field(feed_field: Dict) -> str:
    """entry"""
    enclosures = fetch_enclosures_method(feed_field)
    item = find_item_with_key(enclosures, "href")
    if item is None:
        raise FeedResultFieldNotFoundError(f"Field href not found, {enclosures}")

    url = string_formatter(item.get("href"))
    if not is_url_string(url):
        url = try_fixing_url(url)
    if not is_audio_url(url):
        raise FeedResultTypeError(f"Field href validate error, {url}")
    return url


def get_feed_title_field(feed_field: Dict) -> str:
    """entry"""
    title = feed_field.get("title")
    if title is None:
        raise FeedResultFieldNotFoundError(
            f"Field title not found, {dir_attrs(feed_field)}"
        )
    return string_formatter(title)


def _fetch_content_value_method(feed_entry: Union[FeedParserDict, Dict]) -> str:
    """
    description method

    try finding first item of content field
    {
        "summary": null,
        "content": [
            {
                "type": "application/xhtml+xml",
                "language": null,
                "base": "",
                "value": "<encoded>...</encoded>"
            }
        ]
    }
    """
    content = fetch_content_method(feed_entry)
    item = find_item_with_key(content, "value")
    if item is None:
        raise FeedResultFieldNotFoundError(
            f"Field value not found, {[{i: d.keys()} for i, d in enumerate(content, 1)]}"
        )
    return html_to_string_formatter(item.get("value"))


def _try_multiple_methods_for_description(
    feed_entry: Union[FeedParserDict, Dict],
) -> List[str]:
    matched_methods = [
        fetch_subtitle_method,
        fetch_summary_method,
        fetch_description_method,
        _fetch_content_value_method,
    ]
    return apply_methods_to_get_all_result(matched_methods, feed_entry)


def get_feed_description_description(feed_field: Dict) -> str:
    """entry"""
    description_list = _try_multiple_methods_for_description(feed_field)
    if len(description_list) == 0:
        raise FeedResultFieldNotFoundError(
            f"Field description not found, {dir_attrs(feed_field)}"
        )
    formatted_description_list = apply_method_with_list_to_get_all_result(
        description_list, string_formatter
    )
    formatted_description_list = apply_method_with_list_to_get_all_result(
        formatted_description_list, remove_html_tag_formatter
    )
    sorted_description_list = sorted(formatted_description_list, key=len, reverse=True)
    return sorted_description_list[0]


def _try_multiple_methods_for_release_date(feed_field: Dict) -> List[str]:
    matched_methods = [fetch_published_method, fetch_pub_date_method]
    return apply_methods_to_get_all_result(matched_methods, feed_field)


def _convert_release_date(release_date: str) -> str:
    covert_funcs = [
        basic_datetime_formatter,
        fix_short_month_datetime_formatter,
        fix_week_alias_datetime_formatter,
    ]
    for func in covert_funcs:
        try:
            return func(release_date)
        except FormatterException as exc:
            logger.debug("formatter error, function: %s, %s", func.__name__, exc)
        except Exception as exc:
            logger.error("unexpected error, %s", exc)
            raise Exception(f"Unexpected error, {exc}") from exc
    raise FeedResultFieldNotFoundError("Convert error, cant parse release_date")


def get_feed_release_date_field(feed_field: Dict) -> str:
    release_date_list = _try_multiple_methods_for_release_date(feed_field)
    if len(release_date_list) == 0:
        raise FeedResultFieldNotFoundError(
            f"Field release_date is empty, {dir_attrs(feed_field)}"
        )
    release_date = release_date_list[0]
    release_date = string_formatter(release_date)
    release_date = _convert_release_date(release_date)
    return release_date


def get_feed_duration_field(feed_field: Dict) -> str:
    duration = fetch_itunes_duration_method(feed_field)
    return duration_formatter(trim_string(duration))


def _convert_tag(term_string: str) -> List[str]:
    tags = []
    if has_string(term_string):
        tags.extend(
            [
                string_formatter(term)
                for term in term_string.split(" ")
                if term is not None and term != ""
            ]
        )
    elif string_formatter(term_string).lower() != "podcast":
        tags.append(string_formatter(term_string))
    return tags


def get_feed_tag_field(feed_field: Dict) -> List[str]:
    tag_list = fetch_tags_method(feed_field)
    if len(tag_list) == 0:
        raise FeedResultFieldNotFoundError(
            f"Field tags is empty, {dir_attrs(feed_field)}"
        )
    if not isinstance(tag_list, list):
        return []
    tags = []
    for tag in tag_list:
        try:
            term = fetch_term_method(tag)
            if term is None:
                continue
            tags.extend(_convert_tag(term))
        except FormatterException as exc:
            logger.debug("format error, tag: %s, %s", tag, exc)
        except Exception as exc:
            logger.error("unexpected error, %s", exc)
    return tags
