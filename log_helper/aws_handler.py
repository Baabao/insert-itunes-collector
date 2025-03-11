# type: ignore
import abc
import logging
import traceback

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from core.conf import settings


class AWSHandler(logging.StreamHandler, abc.ABC):
    def __init__(self, **kwargs):
        # By default, logging.StreamHandler uses sys.stderr if stream parameter is not specified
        logging.StreamHandler.__init__(self)

        try:
            self.build(**kwargs)
        except Exception as _:
            print("unexpected error, %s" % (traceback.format_exc(10),))

    @abc.abstractmethod
    def build(self, **kwargs) -> bool:
        pass

    def get_aws_region_name(self) -> str:
        return settings.REGION_NAME

    def get_aws_access_key_id(self) -> str:
        return settings.AWS_ACCESS_KEY_ID

    def get_aws_secret_access_key(self) -> str:
        return settings.AWS_SECRET_ACCESS_KEY


class FirehoseHandler(AWSHandler):
    __firehose = None
    __stream_buffer = []
    __delivery_stream_name = None

    def build(self, stream_name: str) -> bool:
        try:
            self.__firehose = boto3.client(
                "firehose",
                aws_access_key_id=self.get_aws_access_key_id(),
                aws_secret_access_key=self.get_aws_secret_access_key(),
                region_name=self.get_aws_region_name(),
            )
            self.__delivery_stream_name = stream_name
            return True
        except ClientError as exc:
            print("firehose client initialization failed, %s" % (str(exc),))
        except BotoCoreError as e:
            print("boto error, %s" % (str(e),))

    def emit(self, record):
        try:
            msg = self.format(record)

            if self.__firehose:
                self.__stream_buffer.append(
                    {"Data": msg.encode(encoding="UTF-8", errors="strict")}
                )
            else:
                stream = self.stream
                stream.write(msg)
                stream.write(self.terminator)

            self.flush()

        except Exception as _:
            self.handleError(record)

    def flush(self):
        self.acquire()

        try:
            if self.__firehose and self.__stream_buffer:
                self.__firehose.put_record_batch(
                    DeliveryStreamName=self.__delivery_stream_name,
                    Records=self.__stream_buffer,
                )

                self.__stream_buffer.clear()

        except Exception as _:
            print(f"operation error, stream_buffer: {self.__stream_buffer}")

        finally:
            if self.stream and hasattr(self.stream, "flush"):
                self.stream.flush()

            self.release()
