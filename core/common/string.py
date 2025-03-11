import re
from typing import AnyStr
from urllib.parse import urlparse, urlunparse


def to_utf8_string(value: AnyStr) -> str:
    """
    Convert any input to a properly encoded UTF-8 string.

    Args:
        value: The input value, which may be bytes, str, or other types.

    Returns:
        str: A UTF-8 encoded string.
    """
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="ignore")
    if isinstance(value, str):
        return value
    return str(value)


def trim_string(value: str) -> str:
    return str(value).strip()


def is_ascii_string(string: str) -> bool:
    return all(ord(s) < 128 for s in string)


def is_byte_string(string: AnyStr) -> bool:
    return isinstance(string, bytes)


def is_url_string(string: str) -> bool:
    pattern = (
        r"^(https?:\/\/[\w\-\.]+(:\d+)?(\/[~\w\/\.\-%\+, :\(\)\=]*)?(\?\S*)?(#\S*)?)$"
    )
    return re.match(pattern, string) is not None


def is_empty_string(string: str) -> bool:
    return string is None or trim_string(string) == ""


def is_email(string: str) -> bool:
    return bool(re.match(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$", string))


def is_audio_url(string: str) -> bool:
    if not is_url_string(string):
        return False
    if re.search(
        r"\.(flac|wav|aiff|aif|alac|mp3|aac|ogg|wma|opus|m4a|amr|mid|midi|caf|ra)(\?.*)?$",
        string,
    ):
        return True
    return False


def try_fixing_url(url: str) -> str:
    """
    Fix url about host, port...
    :param url: str
    :return: str
    """
    scheme, netloc, path, params, query, fragment = urlparse(url)
    if not scheme:
        scheme = "http"
    if not netloc:
        netloc, path = path, ""
    return urlunparse((scheme, netloc, path, params, query, fragment))
