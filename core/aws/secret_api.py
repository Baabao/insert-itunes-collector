import json
import typing

from core.aws.session import get_aws_session


def get_aws_secret(
    secret_id: str, aws_access_key_id: str, aws_secret_access_key: str, region_name: str
) -> typing.Dict:
    session = get_aws_session()
    session_client = session.client(
        service_name="secretsmanager",
        aws_access_key_id=aws_access_key_id,
        aws_secret_access_key=aws_secret_access_key,
        region_name=region_name,
    )
    session_response = session_client.get_secret_value(SecretId=secret_id)
    return json.loads(session_response["SecretString"])
