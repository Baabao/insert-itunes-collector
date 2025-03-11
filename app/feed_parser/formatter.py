import datetime
import re
from html import unescape

from dateutil import parser
from past.utils import old_div

from app.common.exceptions import FormatterException
from app.feed_parser.parser import CustomizedHTMLParser
from core.common.string import to_utf8_string, trim_string
from log_helper.async_logger import get_async_logger

logger = get_async_logger(__name__)


def string_formatter(string: str) -> str:
    try:
        if not string:
            raise TypeError("empty string")
        return trim_string(to_utf8_string(string))

    except (FormatterException, TypeError) as exc:
        logger.debug("format error, %s", exc)
        raise FormatterException("Format error, %s" % (exc,)) from exc

    except Exception as exc:
        logger.debug("unexpected error", exc)
        raise FormatterException("Format error, %s" % (exc,)) from exc


def remove_html_tag_formatter(string: str) -> str:
    try:
        if string is None:
            raise TypeError("empty string")
        if not isinstance(string, str):
            raise TypeError("unsupported type")
        html_tag_pattern = re.compile(r"<.*?>")
        new_string = re.sub(html_tag_pattern, "", string)
        return new_string

    except (FormatterException, TypeError) as exc:
        logger.debug("format error, %s", exc)
        raise FormatterException("Format error, %s" % (exc,)) from exc

    except Exception as exc:
        raise FormatterException("Format error, %s" % (exc,)) from exc


def html_to_string_formatter(html_string: str) -> str:
    """
    處理 Entry Content 的 Value - 該 value 可能包含 encode 的 HTML, 故增加以下處理流程，將之轉為較乾淨 text
    """
    try:
        if html_string is None:
            raise TypeError("empty string")
        if not isinstance(html_string, str):
            raise TypeError("unsupported type")

        # decode (如果有 encode 的 HTML，先 decode). 3.4＋ 參考： https://docs.python.org/zh-tw/3.8/library/html.html
        value = unescape(html_string)
        value = unescape(value)  # 多 decode 一次 - 如果原 data 有二次 encode 的話

        # 透過 html.HTMLParser 的解析過程，擷取純文字的部分. 參考 python html document: https://docs.python.org/zh-tw/3.8/library/html.parser.html， 優勢 (1) 內建 (2) 處理不完整 tag 也沒什麼問題
        html_parser_instance = CustomizedHTMLParser()
        html_parser_instance.feed(value)

        if not hasattr(html_parser_instance, "text"):
            # 沒有 .text property -> 有問題， raise exception
            raise FormatterException(
                "formatter failure - lose text, %s",
                CustomizedHTMLParser.__class__.__name__,
            )

        text = html_parser_instance.text

        # # 需要時請自行打開註解，以觀察第一次 HTML 清除效果
        # print(' 第一次解析: ', html_parser_instance.text)

        # 再處理一次 - 如果有殘留 html tag 的話 (目前除了 script, style 的內容外，其他的 children)
        # TODO: might use while loop, use re to filter <tag>
        html_parser_instance.reset()
        html_parser_instance.feed(text)

        if not hasattr(html_parser_instance, "text"):
            # 沒有 .text property -> 有問題， raise exception
            raise FormatterException(
                "formatter failure again - lose text, %s",
                CustomizedHTMLParser.__class__.__name__,
            )

        # # 需要時請自行打開註解，以觀察第一次、第二次的 HTML 清除效果
        # print(' 第二次解析: ', html_parser_instance.text)

        return html_parser_instance.text

    except (FormatterException, TypeError) as exc:
        logger.debug("format error, %s", exc)
        raise FormatterException("Format error, %s" % (exc,)) from exc

    except Exception as exc:
        logger.error("unexpected error", exc)
        raise FormatterException("Format error, %s" % (exc,)) from exc


# TODO: python >= 3.10 throw "AttributeError 'collections' has no attribute 'Callable'
def basic_datetime_formatter(dt_string: str) -> str:
    try:
        dt = parser.parse(dt_string)
        # If the time string does not contain timezone information, treat it as UTC.
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=datetime.timezone.utc)
        else:
            # Convert the time with timezone information to UTC.
            dt = dt.astimezone(datetime.timezone.utc)
        return dt.strftime("%Y/%m/%d %H:%M:%S")
    except Exception as exc:
        logger.debug("unexpected error", exc)
        raise FormatterException("Format error, %s" % (exc,)) from exc


def fix_short_month_datetime_formatter(dt_string: str) -> str:
    """
    example: Thu, 15 No 2018 00:00:00 GMT
    """
    short_month_keymap = {
        "Ja": "Jan",
        "Fe": "Feb",
        "Ap": "Apr",
        "Au": "Aug",
        "Se": "Sep",
        "Oc": "Oct",
        "No": "Nov",
        "De": "Dec",
    }
    new_dt_string = dt_string
    for k, v in short_month_keymap.items():
        if k not in new_dt_string:
            continue
        new_dt_string = new_dt_string.replace(k, v)
    return basic_datetime_formatter(new_dt_string)


def fix_week_alias_datetime_formatter(dt_string: str) -> str:
    short_week_keymap = {"Tues": "Tue", "Wedn": "Wed", "Thur": "Thu", "Satu": "Sat"}
    new_dt_string = dt_string
    for k, v in short_week_keymap.items():
        if k in new_dt_string:
            new_dt_string = new_dt_string.replace(k, v)
    return basic_datetime_formatter(new_dt_string)


def is_hhmmss_format(string: str) -> bool:
    if re.match(pattern=r"(^\d{1,2}:\d{1,2}:\d{1,2}$)", string=string):
        return True
    return False


def is_mmss_format(string: str) -> bool:
    if re.match(pattern=r"(^\d{1,2}:\d{1,2}$)", string=string):
        return True
    return False


def is_mmmss_format(string: str) -> bool:
    if re.match(pattern=r"(^\d{1,3}:\d{1,2}$)", string=string):
        return True
    return False


def is_hhmmssms_format(string: str) -> bool:
    if re.match(pattern=r"^\d{1,2}:\d{1,2}:\d{1,2}:\d{1,2}$", string=string):
        return True
    return False


def is_hhmmss_dot_ms_format(string: str) -> bool:
    if re.match(pattern=r"^\d{1,2}:\d{1,2}:\d{1,2}.\d{1,2}$", string=string):
        return True
    return False


def is_float_string_format(string: str) -> bool:
    if re.match(pattern=r"^\d+\.\d+$", string=string):
        return True
    return False


def duration_formatter(duration_string: str) -> str:
    """
    Convert text to second
    :param duration_string: str
    :return: int
    """
    if duration_string is None:
        raise TypeError("empty string")
    if not isinstance(duration_string, str):
        raise TypeError("unsupported type")

    new_duration_string = to_utf8_string(duration_string)

    try:
        if is_hhmmss_format(new_duration_string):
            return new_duration_string

        if new_duration_string.isdigit():
            return str(datetime.timedelta(seconds=int(new_duration_string)))

        if is_mmss_format(new_duration_string):
            minute, second = new_duration_string.split(":")
            encode_time = datetime.timedelta(minutes=int(minute), seconds=int(second))
            return str(encode_time)

        if is_mmmss_format(new_duration_string):
            minutes, second = new_duration_string.split(":")
            return f"{old_div(int(minutes), 60)}:{int(minutes) % 60}:{second}"

        if is_hhmmssms_format(new_duration_string):
            hour, minute, second, _ = new_duration_string.split(":")
            return f"{hour}:{minute}:{second}"

        if is_hhmmss_dot_ms_format(new_duration_string):
            fix_duration_string = new_duration_string.replace(".", ":")
            hour, minute, second, _ = fix_duration_string.split(":")
            return f"{hour}:{minute}:{second}"

        if is_float_string_format(new_duration_string):
            return str(datetime.timedelta(seconds=int(float(new_duration_string))))

        raise FormatterException(
            f"unsupported string, duration_string: {duration_string}"
        )

    except (FormatterException, TypeError) as exc:
        logger.debug("format error, %s", exc)
        raise FormatterException("Format error, %s" % (exc,)) from exc

    except Exception as exc:
        logger.error("unexpected error", exc)
        raise FormatterException("Format error, %s" % (exc,)) from exc


def has_string(string: str, length: int = 1) -> bool:
    result = re.findall(r"[\s]{%s}" % (length,), string)
    if len(result) == 0:
        return False
    return True
