import boto3
from boto3 import Session


def get_aws_session() -> Session:
    return boto3.session.Session()
