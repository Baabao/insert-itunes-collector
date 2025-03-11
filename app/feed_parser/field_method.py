from typing import Any, Dict, List

from app.common.exceptions import FeedResultFieldNotFoundError, FeedResultTypeError
from log_helper.utils import dir_attrs

"""
function name convention

def fetch_<field1_>_<field_2>_<field_x>_method():
    ...
"""


def fetch_image_href_method(field: Dict) -> str:
    image = field.get("image")
    if image is None:
        raise FeedResultFieldNotFoundError(
            "field image not found, %s" % (dir_attrs(field),)
        )
    href = image.get("href")
    if href is None:
        raise FeedResultFieldNotFoundError(
            "field href not found, %s" % (dir_attrs(image),)
        )
    return href


def fetch_author_detail_key_method(field: Dict, key: str) -> str:
    author_detail = field.get("author_detail")
    if author_detail is None:
        raise FeedResultFieldNotFoundError(
            "field author_detail not found, %s" % (dir_attrs(field),)
        )
    value = author_detail.get(key)
    if value is None:
        raise FeedResultFieldNotFoundError(
            "field %s not found, %s" % (key, dir_attrs(author_detail))
        )
    return value


def fetch_authors_key_method(field: Dict, key: str) -> str:
    authors = field.get("authors")
    if authors is None:
        raise FeedResultFieldNotFoundError(
            "field authors not found, %s" % (dir_attrs(field),)
        )
    value = None
    if isinstance(authors, dict):
        value = authors.get(key)
    elif isinstance(authors, list):
        for author in authors:
            value = author.get(key)
            if value is not None:
                break
    if value is None:
        raise FeedResultFieldNotFoundError(
            "field %s not found, %s" % (key, dir_attrs(authors))
        )
    return value


def fetch_author_key_method(field: Dict, key: str) -> str:
    author = field.get("author")
    if author is None:
        raise FeedResultFieldNotFoundError(
            "field authors not found, %s" % (dir_attrs(field),)
        )
    value = author.get(key)
    if value is None:
        raise FeedResultFieldNotFoundError(
            "field %s not found, %s" % (key, dir_attrs(author))
        )
    return value


def fetch_enclosures_method(field: Dict) -> List[Any]:
    enclosures = field.get("enclosures")
    if enclosures is None:
        raise FeedResultFieldNotFoundError(
            "field enclosures not found, %s" % (dir_attrs(field),)
        )
    if not isinstance(enclosures, List):
        raise FeedResultTypeError(
            "field enclosures type error, %s" % (type(enclosures),)
        )
    return enclosures


def fetch_subtitle_method(field: Dict) -> str:
    """description method"""

    subtitle = field.get("subtitle")
    if subtitle is None:
        raise FeedResultFieldNotFoundError(
            "field subtitle not found, %s" % (dir_attrs(field),)
        )
    return subtitle


def fetch_summary_method(field: Dict) -> str:
    """description method"""
    summary = field.get("summary")
    if summary is None:
        raise FeedResultFieldNotFoundError(
            "field summary not found, %s" % (dir_attrs(field),)
        )
    return summary


def fetch_description_method(field: Dict) -> str:
    """description method"""

    description = field.get("description")
    if description is None:
        raise FeedResultFieldNotFoundError(
            "field summary not found, %s" % (dir_attrs(field),)
        )
    return description


def fetch_content_method(field: Dict) -> List[Any]:
    content = field.get("content")
    if content is None:
        raise FeedResultFieldNotFoundError(
            "field content not found, %s" % (dir_attrs(field),)
        )
    if not isinstance(content, list):
        raise FeedResultFieldNotFoundError(
            "field content type error, %s" % (type(content),)
        )
    return content


def fetch_published_method(field: Dict) -> str:
    published = field.get("published")
    if published is None:
        raise FeedResultFieldNotFoundError(
            "field published not found, %s" % (dir_attrs(field),)
        )
    return published


def fetch_pub_date_method(field: Dict) -> str:
    pub_date = field.get("pubDate")
    if pub_date is None:
        raise FeedResultFieldNotFoundError(
            "field pubDate not found, %s" % (dir_attrs(field),)
        )
    return pub_date


def fetch_itunes_duration_method(field: Dict) -> str:
    itunes_duration = field.get("itunes_duration")
    if itunes_duration is None:
        raise FeedResultFieldNotFoundError(
            "field itunes_duration not found, %s" % (dir_attrs(field),)
        )
    return itunes_duration


def fetch_tags_method(field: Dict) -> List[Any]:
    tags = field.get("tags")
    if tags is None:
        raise FeedResultFieldNotFoundError(
            "field tags not found, %s" % (dir_attrs(field),)
        )
    return tags


def fetch_term_method(field: Dict) -> str:
    term = field.get("term")
    if term is None:
        raise FeedResultFieldNotFoundError(
            "field term not found, %s" % (dir_attrs(field),)
        )
    return term
