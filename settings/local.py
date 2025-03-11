from core.conf.helper import get_env

PROD = "local"

AWS_ACCESS_KEY_ID = get_env("AWS_ACCESS_KEY_ID", required=False)
AWS_SECRET_ACCESS_KEY = get_env("AWS_SECRET_ACCESS_KEY", required=False)
REGION_NAME = get_env("REGION", "us-west-2", required=False)

DATABASE = {
    # Using Key=VALUE pattern, https://www.postgresql.org/docs/current/libpq-connect.html#LIBPQ-CONNSTRING-KEYWORD-VALUE
    "DSN": "host='localhost' dbname='baabaodb2' user='jack' port=5432",
}

CACHE = {
    "ENDPOINT_URL": "127.0.0.1",
    "DB": {
        # number must map real redis db
        0: {"NAME": "django", "PREFIX": ""},
        1: {"NAME": "insert_itunes_collector", "PREFIX": "insert_itunes_collector"},
    },
}
