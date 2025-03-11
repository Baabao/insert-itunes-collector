import logging.config
from typing import Dict

from log_helper.utils import resolve_file_path


def setup_logging(config: Dict) -> None:
    logging.config.dictConfig(resolve_file_path(config))
