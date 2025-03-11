import os

#  never move
PROJECT_PATH = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

EXECUTION_PATH = os.path.join(PROJECT_PATH, "execution")

LOG_PATH = os.path.join(PROJECT_PATH, "logs")

APPS_PATH = os.path.join(PROJECT_PATH, "apps")

DATA_PATH = os.path.join(PROJECT_PATH, "data")

ITUNES_COLLECTION_PATH = os.path.join(DATA_PATH, "itunes_data")
ITUNES_TAGS_PATH = os.path.join(DATA_PATH, "tag_data")
ITUNES_TAGS_FILE_PATH = os.path.join(ITUNES_TAGS_PATH, "tags.json")

FEED_DATA_PATH = os.path.join(DATA_PATH, "feed_data")

# created by code

waited_creating_list = [
    DATA_PATH,
    ITUNES_COLLECTION_PATH,
    ITUNES_TAGS_PATH,
    FEED_DATA_PATH,
    LOG_PATH,
]


def check_and_create_path() -> None:
    for check_path in waited_creating_list:
        if not os.path.exists(check_path):
            os.makedirs(check_path)


check_and_create_path()

ITUNES_GENRE_CACHE_TIMEOUT = 86400

DJANGO_CACHE_DB_NUMBER = 0
ITUNES_CACHE_DB_NUMBER = 1
