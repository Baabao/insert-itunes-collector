import random
from typing import Dict, List


def create_headers(accept: str, language: str, user_agent: str) -> Dict:
    return {
        "Accept": accept,
        "Accept-Language": language,
        "Accept-Encoding": "gzip, deflate, br",
        "User-Agent": user_agent,
    }


def create_common_header() -> Dict:
    return create_headers(
        accept="text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        language="en,zh-TW;q=0.5",
        user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/39.0.2171.95 Safari/537.36",
    )


def _get_agent_samples() -> List[str]:
    return [
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/39.0.2171.95 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:95.0) Gecko/20100101 Firefox/95.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.2 Safari/605.1.15",
    ]


def _get_accept_samples() -> List[str]:
    return [
        "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9",
        "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    ]


def _get_lang_samples() -> List[str]:
    return ["zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7", "en,zh-TW;q=0.5"]


def get_random_agent() -> str:
    return random.choice(_get_agent_samples())


def get_random_accept() -> str:
    return random.choice(_get_accept_samples())


def get_random_lang() -> str:
    return random.choice(_get_lang_samples())


def get_random_header() -> Dict:
    return create_headers(
        accept=get_random_accept(),
        language=get_random_lang(),
        user_agent=get_random_agent(),
    )
