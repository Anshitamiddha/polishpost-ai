"""A fake Backblaze B2 client for tests.

It answers the two calls the storage service makes (HeadBucket and PutObject),
records them, and can be told to fail. Nothing touches the network.
"""

from types import SimpleNamespace

from botocore import exceptions as boto_errors

BUCKET = "test-bucket"
ENDPOINT = "https://s3.test-001.backblazeb2.com"


def client_error(status: int, code: str = "Failure", operation: str = "PutObject", message: str = "private-detail"):
    """The error boto3 raises when B2 answers with a failure."""
    return boto_errors.ClientError(
        {"Error": {"Code": code, "Message": message}, "ResponseMetadata": {"HTTPStatusCode": status}},
        operation,
    )


class FakeB2Client:
    def __init__(self):
        self.meta = SimpleNamespace(endpoint_url=ENDPOINT, region_name="test-001")
        self.calls: list[str] = []
        self.head_calls: list[dict] = []
        self.puts: list[dict] = []
        # Set to an exception to make that call fail.
        self.head_error: Exception | None = None
        self.put_error: Exception | None = None
        # Called just before HeadBucket answers, so a test can see what had happened by then.
        self.on_head = None

    def head_bucket(self, **kwargs):
        self.calls.append("head_bucket")
        self.head_calls.append(kwargs)
        if self.on_head:
            self.on_head()
        if self.head_error:
            raise self.head_error
        return {}

    def put_object(self, *, Bucket, Key, Body, ContentType):
        self.calls.append("put_object")
        data = Body.read()  # read it like the real client would
        if self.put_error:
            raise self.put_error
        self.puts.append({"bucket": Bucket, "key": Key, "content_type": ContentType, "body": data})
        return {"ETag": '"fake-etag"'}
