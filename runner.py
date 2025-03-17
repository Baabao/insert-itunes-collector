import datetime
import logging
import time

from app.main import entry_point
from config.loader import execution
from log_helper import setup_logging

logger = logging.getLogger("runner")


def execute():
    while True:
        try:
            runner_config = execution.runner

            if not runner_config.continue_execute:
                logger.info("Job will shutdown in 30 seconds.")
                time.sleep(30)
                break

            time.sleep(runner_config.prepare_interval)

            logger.info("Job starting")

            entry_point()

            logger.info("Job ended")

            time.sleep(runner_config.post_interval)

        except Exception as exc:
            logger.exception(exc)


if __name__ == "__main__":
    setup_logging(execution.logger)
    execute()
