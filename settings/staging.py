from core.aws.secret_api import get_aws_secret
from core.conf.helper import get_env

PROD = "staging"

AWS_ACCESS_KEY_ID = get_env("AWS_ACCESS_KEY_ID", required=False)
AWS_SECRET_ACCESS_KEY = get_env("AWS_SECRET_ACCESS_KEY", required=False)
REGION_NAME = get_env("REGION", "us-west-2", required=False)

_POSTGRES_SECRET_ID = get_env("POSTGRES_SECRET_ID")

_SECRET = get_aws_secret(
    _POSTGRES_SECRET_ID,
    AWS_ACCESS_KEY_ID,
    AWS_SECRET_ACCESS_KEY,
    REGION_NAME,
)

DATABASE = {
    # Using Key=VALUE pattern, https://www.postgresql.org/docs/current/libpq-connect.html#LIBPQ-CONNSTRING-KEYWORD-VALUE
    "DSN": f"host='{_SECRET['host']}' "
    f"dbname='{_SECRET['dbname']}' "
    f"user='{_SECRET['user']}' "
    f"password='{_SECRET['password']}' "
    f"port='{_SECRET['port']}'",
}


CACHE = {
    "ENDPOINT": get_env("CACHE_ENDPOINT"),
    "DB": {
        # number must map real redis db
        0: {"NAME": "django", "PREFIX": ""},
        1: {"NAME": "insert_itunes_collector", "PREFIX": "insert_itunes_collector"},
    },
}
