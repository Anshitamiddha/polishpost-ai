"""Tests for the whole flow: Magic Hour makes the picture, then B2 stores it.

The real Magic Hour SDK runs against a local fake server (magic_hour_fake.py) and
B2 is a fake client (b2_fake.py). Nothing leaves this computer and nothing is charged.
"""

import json
import logging
from datetime import datetime
from unittest.mock import MagicMock

import pytest
from botocore import exceptions as boto_errors
from magic_hour import Client

from app.schemas.thumbnail import ThumbnailRequest
from app.services import thumbnail_generation_service as service_module
from app.services.b2_storage_service import B2StorageService
from app.services.errors import (
    ImageGeneratedButNotStoredError,
    ImageNotCreatedError,
    InvalidModelOutputError,
    ProviderRateLimitError,
    StorageAuthError,
    StorageNotConfiguredError,
    StorageRequestError,
    StorageTimeoutError,
    StorageUnavailableError,
)
from app.services.thumbnail_generation_service import PENDING_UPLOAD_ENDING, ThumbnailGenerationService
from b2_fake import BUCKET, ENDPOINT, FakeB2Client, client_error
from magic_hour_fake import FakeMagicHour, image_bytes

# Fake values made for these tests only. Nothing here is a real secret.
KEY = "mh-SUPER-SECRET-key-123"


def request(workspace_id: int = 12) -> ThumbnailRequest:
    return ThumbnailRequest(
        workspace_id=workspace_id,
        video_topic="Sunrise hike in the Alps",
        heading="ALPS AT DAWN",
        visual_style="cinematic, golden light",
    )


@pytest.fixture
def fake():
    server = FakeMagicHour().start()
    yield server
    server.stop()


@pytest.fixture
def b2():
    return FakeB2Client()


@pytest.fixture
def output_dir(tmp_path):
    return tmp_path / "thumbnails"


@pytest.fixture
def make_service(fake, b2, output_dir):
    def build(storage=None):
        client = Client(token=KEY, base_url=fake.url, timeout=5)
        return ThumbnailGenerationService(
            client,
            model="z-image-turbo",
            resolution="640px",
            output_dir=output_dir,
            timeout_seconds=5.0,
            poll_interval_seconds=0.01,
            storage=storage or B2StorageService(b2, BUCKET),
        )

    return build


def files_in(folder):
    return sorted(p.name for p in folder.iterdir()) if folder.exists() else []


def pictures_in(folder):
    return [name for name in files_in(folder) if not name.endswith(PENDING_UPLOAD_ENDING)]


# --- a good run -----------------------------------------------------------------------


def test_a_good_run_uploads_the_checked_picture_under_the_workspace_key(make_service, b2, output_dir):
    result = make_service().generate(request(workspace_id=42))

    image = result.image
    local = output_dir / image.reference
    (put,) = b2.puts
    assert image.object_key == f"workspaces/42/generated/{image.asset_id}.png"
    assert (put["bucket"], put["key"], put["content_type"]) == (BUCKET, image.object_key, "image/png")
    # What B2 received is exactly the checked file, and the local copy stays.
    assert put["body"] == local.read_bytes()
    assert image.asset_id == local.stem
    assert image.size_bytes == local.stat().st_size == len(put["body"])
    assert image.content_type == "image/png"
    assert (image.width, image.height, image.format) == (640, 360, "png")
    assert files_in(output_dir) == [image.reference]


@pytest.mark.parametrize(
    "pillow_format, ending, content_type, reported",
    [("PNG", "png", "image/png", "png"), ("JPEG", "jpg", "image/jpeg", "jpeg"), ("WEBP", "webp", "image/webp", "webp")],
)
def test_the_real_format_decides_the_key_ending_and_content_type(
    fake, make_service, b2, pillow_format, ending, content_type, reported
):
    fake.file_reply = (200, image_bytes(pillow_format))

    result = make_service().generate(request())

    assert result.image.object_key.endswith(f"/{result.image.asset_id}.{ending}")
    assert result.image.reference.endswith(f".{ending}")
    assert result.image.content_type == content_type
    assert result.image.format == reported
    assert b2.puts[0]["content_type"] == content_type


def test_storage_is_checked_before_magic_hour_is_asked_for_anything(fake, make_service, b2):
    seen = []
    b2.on_head = lambda: seen.append(len(fake.requests))

    make_service().generate(request())

    assert seen == [0]  # no request had reached Magic Hour when B2 was checked
    assert b2.calls == ["head_bucket", "put_object"]


def test_each_picture_gets_its_own_key_so_nothing_is_overwritten(make_service, b2):
    service = make_service()

    first = service.generate(request())
    second = service.generate(request())

    assert first.image.object_key != second.image.object_key
    assert len({put["key"] for put in b2.puts}) == 2


def test_the_workspace_id_comes_from_the_request_and_nowhere_else(make_service, b2):
    make_service().generate(request(workspace_id=7))
    make_service().generate(request(workspace_id=8))

    assert [put["key"].split("/")[1] for put in b2.puts] == ["7", "8"]


def test_nothing_in_the_answer_is_a_link_or_a_path(make_service, output_dir):
    text = make_service().generate(request()).model_dump_json()

    assert "http" not in text
    assert BUCKET not in text and ENDPOINT not in text
    assert str(output_dir) not in text and str(output_dir.parent) not in text


# --- pictures that are not valid are never uploaded --------------------------------------


@pytest.mark.parametrize(
    "reply",
    [
        (404, b"gone"),
        (500, b"oops"),
        (200, b"this is not a picture"),
        (200, image_bytes("PNG")[:200]),  # cut off half way
        (200, image_bytes("GIF")),  # a real image, but not a format we accept
        (200, b""),
        (200, image_bytes("PNG", size=(50, 30))),  # too small to be a thumbnail
    ],
    ids=["link-gone", "download-error", "not-an-image", "truncated", "unsupported-format", "empty", "tiny"],
)
def test_an_invalid_picture_is_never_uploaded(fake, make_service, b2, output_dir, reply):
    fake.file_reply = reply

    with pytest.raises(Exception):
        make_service().generate(request())

    assert b2.puts == []
    assert files_in(output_dir) == []


def test_a_file_over_the_size_limit_is_never_uploaded(make_service, b2, monkeypatch):
    monkeypatch.setattr(service_module, "MAX_FILE_BYTES", 100)

    with pytest.raises(InvalidModelOutputError):
        make_service().generate(request())

    assert b2.puts == []


def test_a_failed_generation_never_reaches_storage(fake, make_service, b2):
    fake.create_reply = (429, {"message": "slow down"})

    with pytest.raises(ProviderRateLimitError):
        make_service().generate(request())

    assert b2.calls == ["head_bucket"]  # only the check before paying


def test_a_job_that_ends_in_error_never_reaches_storage(fake, make_service, b2):
    fake.poll_replies = [fake.project("error", error={"code": "x", "message": "refused"})]

    with pytest.raises(ImageNotCreatedError):
        make_service().generate(request())

    assert b2.puts == []


# --- storage is not ready: nothing is paid for ---------------------------------------------


@pytest.mark.parametrize(
    "error, expected",
    [
        (client_error(403, "AccessDenied", "HeadBucket"), StorageAuthError),
        (client_error(404, "NoSuchBucket", "HeadBucket"), StorageNotConfiguredError),
        (client_error(503, "ServiceUnavailable", "HeadBucket"), StorageUnavailableError),
        (boto_errors.ConnectTimeoutError(endpoint_url=ENDPOINT), StorageTimeoutError),
        (boto_errors.EndpointConnectionError(endpoint_url=ENDPOINT), StorageUnavailableError),
    ],
    ids=["refused", "no-bucket", "outage", "timeout", "unreachable"],
)
def test_storage_trouble_stops_everything_before_any_paid_job(fake, make_service, b2, output_dir, error, expected):
    b2.head_error = error

    with pytest.raises(expected) as caught:
        make_service().generate(request())

    assert type(caught.value) is expected
    assert fake.requests == []  # Magic Hour was never asked, so nothing was charged
    assert b2.puts == []
    assert not output_dir.exists()  # not even the folder


# --- generated, but the upload failed --------------------------------------------------------


@pytest.mark.parametrize(
    "error, cause",
    [
        (client_error(403, "AccessDenied"), StorageAuthError),
        (boto_errors.ConnectTimeoutError(endpoint_url=ENDPOINT), StorageTimeoutError),
        (boto_errors.EndpointConnectionError(endpoint_url=ENDPOINT), StorageUnavailableError),
        (client_error(400, "InvalidRequest"), StorageRequestError),
    ],
    ids=["refused", "timeout", "unreachable", "bad-request"],
)
def test_a_failed_upload_keeps_the_paid_picture_and_says_so(fake, make_service, b2, output_dir, error, cause):
    b2.put_error = error

    with pytest.raises(ImageGeneratedButNotStoredError) as caught:
        make_service().generate(request(workspace_id=5))

    assert type(caught.value.__cause__) is cause
    assert "generated" in str(caught.value) and "stored" in str(caught.value)
    assert len(fake.creates()) == 1  # paid exactly once, and not asked again
    (picture,) = pictures_in(output_dir)
    note_path = output_dir / f"{picture.rsplit('.', 1)[0]}{PENDING_UPLOAD_ENDING}"
    # Nothing else is left behind: no temporary folder and no half-written note.
    assert files_in(output_dir) == sorted([picture, note_path.name])

    note = json.loads(note_path.read_text(encoding="utf-8"))
    asset_id = picture.rsplit(".", 1)[0]
    assert note["asset_id"] == asset_id
    assert note["workspace_id"] == 5
    assert note["object_key"] == f"workspaces/5/generated/{asset_id}.png"
    assert note["local_file"] == picture
    assert (note["width"], note["height"], note["format"]) == (640, 360, "png")
    assert note["provider_generation_id"] == "job-1" and note["credits_charged"] == 5
    assert note["failure"] == cause.__name__  # the storage error that stopped the upload
    datetime.fromisoformat(note["failed_at"])


def test_the_note_and_the_local_file_are_enough_to_upload_it_later(fake, make_service, b2, output_dir):
    b2.put_error = client_error(503, "ServiceUnavailable")
    with pytest.raises(ImageGeneratedButNotStoredError):
        make_service().generate(request(workspace_id=9))
    (note_path,) = [output_dir / n for n in files_in(output_dir) if n.endswith(PENDING_UPLOAD_ENDING)]
    note = json.loads(note_path.read_text(encoding="utf-8"))

    # Later, with B2 working again, no new picture is needed.
    working = FakeB2Client()
    extension = note["local_file"].rsplit(".", 1)[1]
    stored = B2StorageService(working, BUCKET).upload_image(
        output_dir / note["local_file"], note["workspace_id"], note["asset_id"], extension
    )

    assert stored.object_key == note["object_key"]
    assert len(fake.creates()) == 1


def test_the_note_and_the_log_hold_no_secrets_and_no_paths(fake, make_service, b2, output_dir, caplog):
    caplog.set_level(logging.DEBUG)
    b2.put_error = client_error(403, "AccessDenied", message=f"private-detail {KEY}")

    with pytest.raises(ImageGeneratedButNotStoredError) as caught:
        make_service().generate(request())

    (note_path,) = [output_dir / n for n in files_in(output_dir) if n.endswith(PENDING_UPLOAD_ENDING)]
    note_text = note_path.read_text(encoding="utf-8")
    for text in (note_text, str(caught.value)):
        assert KEY not in text and "private-detail" not in text
        assert str(output_dir) not in text
    assert KEY not in caplog.text and "Bearer" not in caplog.text
    # The log has what is needed to find and retry the picture.
    assert json.loads(note_text)["asset_id"] in caplog.text
    assert "kept locally for a retry" in caplog.text


def test_a_note_that_cannot_be_written_does_not_hide_the_real_error(fake, make_service, b2, output_dir, caplog, monkeypatch):
    real_write_text = service_module.Path.write_text

    def refuse_notes(self, *args, **kwargs):
        if self.name.endswith(".tmp"):
            raise PermissionError("access denied: C:/private/place")
        return real_write_text(self, *args, **kwargs)

    monkeypatch.setattr(service_module.Path, "write_text", refuse_notes)
    caplog.set_level(logging.DEBUG)
    b2.put_error = boto_errors.ConnectTimeoutError(endpoint_url=ENDPOINT)

    with pytest.raises(ImageGeneratedButNotStoredError):
        make_service().generate(request())

    (picture,) = files_in(output_dir)  # the picture is kept, and there is no stray note
    assert picture.endswith(".png")
    assert "Could not write the retry note" in caplog.text
    assert picture.rsplit(".", 1)[0] in caplog.text  # the log still names the picture


def test_an_unexpected_upload_failure_also_keeps_the_picture(fake, make_service, output_dir):
    storage = MagicMock(spec=B2StorageService)
    storage.upload_image.side_effect = RuntimeError("a bug")

    with pytest.raises(RuntimeError):  # shown as it is, so the bug is not hidden
        make_service(storage).generate(request())

    assert len(pictures_in(output_dir)) == 1
    assert len(files_in(output_dir)) == 2  # the picture and its note


def test_the_storage_gets_the_final_local_file_not_the_temporary_download(fake, make_service, output_dir):
    storage = MagicMock(spec=B2StorageService)
    seen = {}

    def upload(path, *args):
        seen["path"], seen["exists"], seen["parent"] = path, path.is_file(), path.parent
        return MagicMock(object_key="k", content_type="image/png", size_bytes=1)

    storage.upload_image.side_effect = upload

    make_service(storage).generate(request(workspace_id=3))

    assert seen["exists"] and seen["parent"] == output_dir
    assert not seen["path"].parent.name.startswith(".incoming")
    storage.upload_image.assert_called_once()
    assert storage.upload_image.call_args.args[1] == 3  # the workspace id
