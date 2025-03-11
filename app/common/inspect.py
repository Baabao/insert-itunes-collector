import timeit

from log_helper.async_logger import get_async_logger

logger = get_async_logger(__name__)


def diff_time(last_time: float, point: int = 3) -> float:
    if not isinstance(last_time, float):
        raise TypeError("wrong last_time value %s", last_time)
    diff = timeit.default_timer() - last_time
    return round(diff, point) if diff > 0 else 0


def calc_deco(title="calculation"):
    def wrapper_func(func):
        def wrapper(*args, **kwargs):
            with CalcTime(title=title):
                return func(*args, **kwargs)

        return wrapper

    return wrapper_func


class CalcTime(object):
    def __init__(self, title=None):
        self.title = title or "calculation"

    def __enter__(self):
        self.start = timeit.default_timer()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop = timeit.default_timer()
        logger.debug("%s Time: %s", self.title, self.stop - self.start)
