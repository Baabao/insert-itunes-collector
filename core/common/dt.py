from datetime import datetime


def get_current_date_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def get_current_datetime_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
