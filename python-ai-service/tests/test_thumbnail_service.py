"""Tests for the Magic Hour thumbnail service.

The real Magic Hour SDK runs here, pointed at a local fake server (see
magic_hour_fake.py). Nothing leaves this computer and no credits are spent.
"""

import base64
import logging

import pytest
from magic_hour import Client
from pydantic import SecretStr, ValidationError

from app.core.config import Settings
from app.schemas.thumbnail import ThumbnailRequest
from app.services.b2_storage_service import B2StorageService
from app.services import thumbnail_generation_service as service_module
from app.services.errors import (
    ImageNotCreatedError,
    ImageNotSavedError,
    InvalidModelOutputError,
    ProviderAuthError,
    ProviderRateLimitError,
    ProviderRequestError,
    ProviderTimeoutError,
    ProviderUnavailableError,
)
from app.services.thumbnail_generation_service import (
    ThumbnailGenerationService,
    build_prompt,
    get_thumbnail_generation_service,
)
from b2_fake import BUCKET, FakeB2Client
from magic_hour_fake import FakeMagicHour, image_bytes

# Fake values made for these tests only. Nothing here is a real secret.
KEY = "mh-SUPER-SECRET-key-123"
MODEL = "z-image-turbo"
REQUEST = ThumbnailRequest(
    workspace_id=12,
    video_topic="Sunrise hike in the Alps",
    description="You will not believe this view from the top",
    global_prompt="cinematic, golden light, saturated colors",
)


@pytest.fixture
def fake():
    server = FakeMagicHour().start()
    yield server
    server.stop()


@pytest.fixture
def output_dir(tmp_path):
    return tmp_path / "thumbnails"


@pytest.fixture
def b2():
    return FakeB2Client()


@pytest.fixture
def make_service(fake, output_dir, b2):
    def build(*, timeout_seconds=5.0, http_timeout=5.0):
        client = Client(token=KEY, base_url=fake.url, timeout=http_timeout)
        return ThumbnailGenerationService(
            client,
            model=MODEL,
            resolution="640px",
            output_dir=output_dir,
            timeout_seconds=timeout_seconds,
            poll_interval_seconds=0.01,
            storage=B2StorageService(b2, BUCKET),
        )

    return build


def files_in(folder):
    return sorted(p.name for p in folder.iterdir()) if folder.exists() else []


# --- a good run ---------------------------------------------------------------


def test_a_good_run_returns_the_picture_details_and_saves_the_file(fake, make_service, output_dir):
    fake.poll_replies = [fake.project("queued"), fake.project("rendering"), fake.project("complete")]

    result = make_service().generate(REQUEST)

    assert result.success is True
    assert result.status == "complete"
    assert result.provider_generation_id == "job-1"
    assert result.credits_charged == 5
    assert (result.image.width, result.image.height, result.image.format) == (640, 360, "png")
    assert result.image.reference.endswith(".png")
    # The file is really there, and it is the only thing left in the folder.
    assert files_in(output_dir) == [result.image.reference]
    assert len(fake.polls()) == 3


def test_the_request_to_magic_hour_has_the_documented_shape(fake, make_service):
    make_service().generate(REQUEST)

    (create,) = fake.creates()
    body = create["body"]
    assert body["image_count"] == 1
    assert body["aspect_ratio"] == "16:9"
    assert body["model"] == MODEL
    assert body["resolution"] == "640px"
    assert body["style"]["tool"] == "general"
    assert body["name"].startswith("PublishPro thumbnail ")
    # Everything the caller asked for ends up in the prompt.
    prompt = body["style"]["prompt"]
    for wanted in (REQUEST.video_topic, REQUEST.description, REQUEST.global_prompt):
        assert wanted in prompt
    assert create["headers"]["authorization"] == f"Bearer {KEY}"


# --- the picture the page shows ---------------------------------------------------


def test_the_preview_is_the_stored_picture_as_a_data_url(fake, make_service, output_dir):
    result = make_service().generate(REQUEST)

    prefix = "data:image/png;base64,"
    assert result.image.preview_data_url.startswith(prefix)
    shown = base64.b64decode(result.image.preview_data_url[len(prefix):])
    assert shown == (output_dir / result.image.reference).read_bytes()


def test_each_run_previews_its_own_picture_so_a_new_one_replaces_the_old(fake, make_service):
    service = make_service()
    fake.file_reply = (200, image_bytes("PNG", size=(640, 360)))
    first = service.generate(REQUEST)
    fake.file_reply = (200, image_bytes("JPEG", size=(320, 180)))
    second = service.generate(REQUEST)

    assert first.image.preview_data_url != second.image.preview_data_url
    assert first.image.preview_data_url.startswith("data:image/png;base64,")
    assert second.image.preview_data_url.startswith("data:image/jpeg;base64,")


def test_a_picture_that_cannot_be_read_back_is_still_a_stored_thumbnail_without_a_preview(
    fake, make_service, b2, monkeypatch, caplog
):
    def refuse(self):
        raise PermissionError("access denied: C:/private/place")

    monkeypatch.setattr(service_module.Path, "read_bytes", refuse)

    result = make_service().generate(REQUEST)

    assert result.image.preview_data_url is None
    assert len(b2.puts) == 1  # it was still stored
    assert "private" not in caplog.text


def test_a_failed_run_returns_no_preview_at_all(fake, make_service):
    fake.create_reply = (429, {"message": "slow down"})

    with pytest.raises(ProviderRateLimitError):
        make_service().generate(REQUEST)  # an error, so there is no answer a page could show


# --- exactly one picture ----------------------------------------------------------


def test_one_generation_asks_magic_hour_for_exactly_one_picture_and_keeps_one(fake, make_service, b2, output_dir):
    result = make_service().generate(REQUEST)

    (create,) = fake.creates()  # one job per request, never one per variation
    assert create["body"]["image_count"] == 1
    assert len(b2.puts) == 1
    assert files_in(output_dir) == [result.image.reference]


def test_if_magic_hour_ever_lists_two_pictures_only_one_is_kept(fake, make_service, b2, output_dir):
    expires = "2026-11-18T12:00:00Z"
    links = [
        {"url": f"{fake.url}/files/first.png", "expires_at": expires},
        {"url": f"{fake.url}/files/second.png", "expires_at": expires},
    ]
    fake.poll_replies = [fake.project("complete", downloads=links)]

    result = make_service().generate(REQUEST)

    assert len(b2.puts) == 1
    assert files_in(output_dir) == [result.image.reference]  # the second picture is not kept


def test_the_prompt_leaves_out_the_description_and_creative_lines_when_none_are_given():
    bare = ThumbnailRequest(workspace_id=12, video_topic="Sunrise hike")

    assert "About the video" not in build_prompt(bare)
    assert "Creative direction" not in build_prompt(bare)
    assert "About the video" in build_prompt(REQUEST)
    assert "Creative direction" in build_prompt(REQUEST)


# --- the global creative prompt reaches Magic Hour ---------------------------------

# The default text from the Create Post page. It is only test data here: the service
# never contains a prompt of its own, it uses whatever the user wrote.
GLOBAL_PROMPT = (
    "Create a bold, cinematic YouTube thumbnail. Keep the creator as the main focus, "
    "use dramatic lighting, strong contrast, and leave space for a short headline."
)


def request_with_prompt(prompt, **changes):
    values = {
        "workspace_id": 12,
        "video_topic": "AI APP IN 7 DAYS",
        "description": "I built a full AI app in seven days",
        "global_prompt": prompt,
    }
    return ThumbnailRequest(**{**values, **changes})


def prompt_sent_to_magic_hour(fake):
    (create,) = fake.creates()
    return create["body"]["style"]["prompt"]


def test_all_three_inputs_reach_magic_hour_in_one_prompt(fake, make_service):
    make_service().generate(request_with_prompt(GLOBAL_PROMPT))

    assert prompt_sent_to_magic_hour(fake) == (
        'A YouTube thumbnail for a video titled "AI APP IN 7 DAYS". '
        "About the video: I built a full AI app in seven days. "
        f"Creative direction: {GLOBAL_PROMPT} "
        'Write the title "AI APP IN 7 DAYS" in huge, bold, high-contrast letters that are easy to read on a phone. '
        "Keep the layout uncluttered, with one clear main subject. No other text, logos or watermarks."
    )


def test_the_description_is_used_and_a_different_one_gives_a_different_prompt(fake, make_service):
    service = make_service()

    service.generate(request_with_prompt(None, description="a calm morning in the mountains"))
    service.generate(request_with_prompt(None, description="a fast race through a city"))

    first, second = (create["body"]["style"]["prompt"] for create in fake.creates())
    assert "About the video: a calm morning in the mountains." in first and "race" not in first
    assert "About the video: a fast race through a city." in second and "mountains" not in second


def test_the_user_text_is_sent_as_written_so_another_prompt_gives_another_result(fake, make_service):
    service = make_service()

    service.generate(request_with_prompt("soft pastel colors, flat illustration"))
    service.generate(request_with_prompt("dark horror mood, red fog"))

    first, second = (create["body"]["style"]["prompt"] for create in fake.creates())
    assert "soft pastel colors, flat illustration." in first and "horror" not in first
    assert "dark horror mood, red fog." in second and "pastel" not in second


def test_the_service_adds_no_style_of_its_own_that_could_fight_the_user(fake, make_service):
    make_service().generate(request_with_prompt("soft pastel colors"))

    prompt = prompt_sent_to_magic_hour(fake)
    for imposed in ("saturated", "dramatic", "cinematic", "neon"):
        assert imposed not in prompt


def test_without_a_prompt_the_thumbnail_is_still_requested_with_no_direction_line(fake, make_service):
    make_service().generate(request_with_prompt(None))

    prompt = prompt_sent_to_magic_hour(fake)
    assert "Creative direction" not in prompt
    assert "I built a full AI app in seven days" in prompt and "AI APP IN 7 DAYS" in prompt


def test_without_a_description_the_topic_alone_is_enough(fake, make_service):
    make_service().generate(request_with_prompt(GLOBAL_PROMPT, description=None))

    prompt = prompt_sent_to_magic_hour(fake)
    assert "About the video" not in prompt
    assert 'titled "AI APP IN 7 DAYS"' in prompt and GLOBAL_PROMPT in prompt


@pytest.mark.parametrize("ending", [".", "!", "?"])
def test_a_prompt_that_already_ends_like_a_sentence_gets_no_extra_full_stop(ending):
    prompt = build_prompt(request_with_prompt(f"make it pop{ending}"))

    assert f"Creative direction: make it pop{ending} Write the title" in prompt


def test_a_prompt_without_an_ending_gets_a_full_stop():
    assert "Creative direction: make it pop. Write the title" in build_prompt(request_with_prompt("make it pop"))


def test_a_new_picture_never_replaces_an_old_one(fake, make_service, output_dir):
    service = make_service()

    first = service.generate(REQUEST)
    second = service.generate(REQUEST)  # Magic Hour sends the same file name both times

    assert first.image.reference != second.image.reference
    assert files_in(output_dir) == sorted([first.image.reference, second.image.reference])


def test_nothing_in_the_answer_reveals_where_the_file_lives(fake, make_service, output_dir):
    result = make_service().generate(REQUEST)

    text = result.model_dump_json()
    assert str(output_dir) not in text
    assert str(output_dir.parent) not in text
    assert "incoming" not in text
    assert "/" not in result.image.reference and "\\" not in result.image.reference


@pytest.mark.parametrize(
    "image_format, ending, reported",
    [("PNG", ".png", "png"), ("JPEG", ".jpg", "jpeg"), ("WEBP", ".webp", "webp")],
)
def test_the_real_format_decides_the_file_ending(fake, make_service, image_format, ending, reported):
    fake.file_reply = (200, image_bytes(image_format, size=(320, 180)))

    result = make_service().generate(REQUEST)

    assert result.image.reference.endswith(ending)
    assert result.image.format == reported
    assert (result.image.width, result.image.height) == (320, 180)


# --- Magic Hour says no -------------------------------------------------------


@pytest.mark.parametrize(
    "status, expected",
    [
        (401, ProviderAuthError),
        (403, ProviderAuthError),
        (429, ProviderRateLimitError),
        (500, ProviderUnavailableError),
        (503, ProviderUnavailableError),
        (400, ProviderRequestError),
        (422, ProviderRequestError),
    ],
)
def test_a_refusal_when_starting_becomes_the_right_error_and_is_not_retried(fake, make_service, status, expected):
    fake.create_reply = (status, {"message": "sk-provider-detail-that-must-not-leak"})

    with pytest.raises(expected) as caught:
        make_service().generate(REQUEST)

    assert type(caught.value) is expected
    # Magic Hour charges when a job is made, so asking twice could cost twice.
    assert len(fake.creates()) == 1
    assert "sk-provider-detail" not in str(caught.value)
    assert KEY not in str(caught.value)


def test_a_job_that_ends_in_error_becomes_image_not_created(fake, make_service, output_dir):
    fake.poll_replies = [
        fake.project("rendering"),
        fake.project("error", error={"code": "safety", "message": "provider-private-detail"}),
    ]

    with pytest.raises(ImageNotCreatedError) as caught:
        make_service().generate(REQUEST)

    assert "provider-private-detail" not in str(caught.value)
    assert files_in(output_dir) == []


def test_a_canceled_job_becomes_image_not_created(fake, make_service):
    fake.poll_replies = [fake.project("canceled")]

    with pytest.raises(ImageNotCreatedError):
        make_service().generate(REQUEST)


def test_checking_the_job_with_a_bad_key_is_final(fake, make_service):
    fake.poll_replies = [(401, {"message": "no"})]

    with pytest.raises(ProviderAuthError):
        make_service().generate(REQUEST)

    assert len(fake.polls()) == 1


def test_a_hiccup_while_checking_does_not_lose_the_picture(fake, make_service):
    fake.poll_replies = [(503, {"message": "try later"}), fake.project("complete")]

    result = make_service().generate(REQUEST)

    assert result.status == "complete"
    assert len(fake.creates()) == 1  # still only one paid job
    assert len(fake.polls()) == 2


# --- slow answers ------------------------------------------------------------


def test_a_job_that_never_finishes_times_out(fake, make_service, output_dir):
    fake.poll_replies = [fake.project("rendering")]

    with pytest.raises(ProviderTimeoutError):
        make_service(timeout_seconds=0.3).generate(REQUEST)

    assert files_in(output_dir) == []


def test_checking_that_keeps_failing_ends_in_a_timeout_not_a_hang(fake, make_service):
    fake.poll_replies = [(503, {"message": "down"})]

    with pytest.raises(ProviderTimeoutError):
        make_service(timeout_seconds=0.3).generate(REQUEST)


def test_a_slow_call_to_magic_hour_becomes_a_timeout_and_is_not_retried(fake, make_service):
    fake.create_delay_seconds = 0.6

    with pytest.raises(ProviderTimeoutError):
        make_service(http_timeout=0.2).generate(REQUEST)

    assert len(fake.creates()) == 1


def test_an_unreachable_magic_hour_is_a_temporary_outage(output_dir, b2):
    client = Client(token=KEY, base_url="http://127.0.0.1:9", timeout=1)  # nothing listens on port 9
    service = ThumbnailGenerationService(
        client, MODEL, "640px", output_dir, 1.0, 0.01, storage=B2StorageService(b2, BUCKET)
    )

    with pytest.raises(ProviderUnavailableError):
        service.generate(REQUEST)


# --- replies that do not make sense -------------------------------------------


def test_a_start_reply_without_an_id_is_an_invalid_response(fake, make_service):
    fake.create_reply = (200, {"credits_charged": 5, "frame_cost": 5})

    with pytest.raises(InvalidModelOutputError):
        make_service().generate(REQUEST)


def test_a_check_reply_missing_its_fields_is_an_invalid_response(fake, make_service):
    fake.poll_replies = [(200, {"status": "complete"})]

    with pytest.raises(InvalidModelOutputError):
        make_service().generate(REQUEST)


def test_a_reply_that_is_not_json_is_an_invalid_response(fake, make_service):
    fake.create_reply = (200, b"<html>gateway page</html>")

    with pytest.raises(InvalidModelOutputError):
        make_service().generate(REQUEST)


def test_a_finished_job_with_nothing_to_download_is_an_invalid_response(fake, make_service, output_dir):
    fake.poll_replies = [fake.project("complete", downloads=[])]

    with pytest.raises(InvalidModelOutputError):
        make_service().generate(REQUEST)

    assert files_in(output_dir) == []


# --- the downloaded file ------------------------------------------------------


@pytest.mark.parametrize(
    "reply, expected",
    [
        ((404, b"gone"), InvalidModelOutputError),
        ((500, b"oops"), ProviderUnavailableError),
        ((200, b"this is not a picture"), InvalidModelOutputError),
        ((200, image_bytes("PNG")[:200]), InvalidModelOutputError),  # cut off half way
        ((200, image_bytes("GIF")), InvalidModelOutputError),  # a real image, but not a format we accept
        ((200, b""), InvalidModelOutputError),
    ],
    ids=["link-gone", "download-server-error", "not-an-image", "truncated-image", "unsupported-format", "empty-file"],
)
def test_a_bad_download_is_refused_and_leaves_nothing_behind(fake, make_service, output_dir, reply, expected):
    fake.file_reply = reply

    with pytest.raises(expected) as caught:
        make_service().generate(REQUEST)

    assert type(caught.value) is expected
    assert files_in(output_dir) == []  # not even the temporary folder


def test_a_download_that_names_a_file_that_is_not_there_is_refused(fake, make_service, output_dir, monkeypatch):
    ghost = output_dir / "ghost.png"
    monkeypatch.setattr(service_module, "download_files_sync", lambda **kwargs: [str(ghost)])

    with pytest.raises(InvalidModelOutputError):
        make_service().generate(REQUEST)

    assert files_in(output_dir) == []


# --- picture size sanity checks -----------------------------------------------


@pytest.mark.parametrize("size", [(50, 30), (99, 400), (400, 99)], ids=["tiny", "narrow", "short"])
def test_a_picture_too_small_to_be_a_thumbnail_is_refused(fake, make_service, output_dir, size):
    fake.file_reply = (200, image_bytes("PNG", size=size))

    with pytest.raises(InvalidModelOutputError):
        make_service().generate(REQUEST)

    assert files_in(output_dir) == []


def test_the_smallest_accepted_picture_is_100_pixels_on_its_short_side(fake, make_service):
    fake.file_reply = (200, image_bytes("PNG", size=(178, 100)))

    result = make_service().generate(REQUEST)

    assert (result.image.width, result.image.height) == (178, 100)


def test_a_file_over_the_size_limit_is_refused(fake, make_service, output_dir, monkeypatch):
    monkeypatch.setattr(service_module, "MAX_FILE_BYTES", 100)  # far smaller than any real picture

    with pytest.raises(InvalidModelOutputError):
        make_service().generate(REQUEST)

    assert files_in(output_dir) == []


# --- this server's own disk ---------------------------------------------------


def test_an_output_folder_that_cannot_be_made_fails_before_any_paid_job(fake, b2, tmp_path):
    blocker = tmp_path / "blocker"
    blocker.write_text("a file sits where the folder should go")
    client = Client(token=KEY, base_url=fake.url, timeout=5)
    service = ThumbnailGenerationService(
        client, MODEL, "640px", blocker / "thumbnails", 5.0, 0.01, storage=B2StorageService(b2, BUCKET)
    )

    with pytest.raises(ImageNotSavedError):
        service.generate(REQUEST)

    assert fake.creates() == []  # Magic Hour was never asked, so nothing was charged


def test_a_permission_error_on_the_folder_is_the_same_safe_error(fake, make_service, monkeypatch):
    def refuse(self, *args, **kwargs):
        raise PermissionError("access denied: C:/private/place")

    monkeypatch.setattr(service_module.Path, "mkdir", refuse)

    with pytest.raises(ImageNotSavedError) as caught:
        make_service().generate(REQUEST)

    assert fake.creates() == []
    assert "private" not in str(caught.value)


@pytest.mark.parametrize("failing_step", ["write-download", "move-into-place"])
def test_a_disk_error_after_the_job_is_reported_and_leaves_nothing_behind(
    fake, make_service, output_dir, monkeypatch, failing_step
):
    if failing_step == "write-download":

        def refuse(*args, **kwargs):
            raise OSError("disk full: C:/private/place")

        monkeypatch.setattr(service_module, "download_files_sync", refuse)
    else:

        def refuse(self, target):
            raise PermissionError("access denied: C:/private/place")

        monkeypatch.setattr(service_module.Path, "replace", refuse)

    with pytest.raises(ImageNotSavedError) as caught:
        make_service().generate(REQUEST)

    assert "private" not in str(caught.value)
    assert files_in(output_dir) == []  # no temporary folder and no half-saved picture


# --- credentials and settings -------------------------------------------------


@pytest.fixture
def use_settings(monkeypatch):
    def apply(**values):
        monkeypatch.setattr(service_module, "get_settings", lambda: Settings(_env_file=None, **values))
        get_thumbnail_generation_service.cache_clear()

    yield apply
    get_thumbnail_generation_service.cache_clear()


@pytest.mark.parametrize("key", [None, SecretStr(""), SecretStr("   ")], ids=["unset", "empty", "blank"])
def test_a_missing_key_is_refused_before_any_work(use_settings, key):
    use_settings(magic_hour_api_key=key)

    with pytest.raises(ProviderAuthError):
        get_thumbnail_generation_service()


def test_the_shared_service_is_built_once_from_the_settings(use_settings, tmp_path, monkeypatch):
    storage = object()
    monkeypatch.setattr(service_module, "get_b2_storage_service", lambda: storage)
    use_settings(
        magic_hour_api_key=SecretStr(KEY),
        magic_hour_image_model="flux-schnell",
        magic_hour_image_resolution="1k",
        thumbnail_output_dir=tmp_path / "somewhere",
    )

    service = get_thumbnail_generation_service()

    assert service is get_thumbnail_generation_service()
    assert service._model == "flux-schnell"
    assert service._resolution == "1k"
    assert service._output_dir == tmp_path / "somewhere"
    assert service._storage is storage


def test_settings_have_the_supplied_defaults_and_read_the_environment(monkeypatch):
    for name in ("MAGIC_HOUR_API_KEY", "MAGIC_HOUR_IMAGE_MODEL", "MAGIC_HOUR_IMAGE_RESOLUTION", "THUMBNAIL_OUTPUT_DIR"):
        monkeypatch.delenv(name, raising=False)

    defaults = Settings(_env_file=None)
    assert defaults.magic_hour_api_key is None
    assert defaults.magic_hour_image_model == "z-image-turbo"
    assert defaults.magic_hour_image_resolution == "640px"
    # The default folder is inside the project, and the same wherever the service starts.
    assert defaults.thumbnail_output_dir.is_absolute()
    assert defaults.thumbnail_output_dir.parts[-2:] == ("generated", "thumbnails")

    monkeypatch.setenv("MAGIC_HOUR_API_KEY", KEY)
    monkeypatch.setenv("MAGIC_HOUR_IMAGE_RESOLUTION", "1k")
    configured = Settings(_env_file=None)
    assert configured.magic_hour_api_key.get_secret_value() == KEY
    assert configured.magic_hour_image_resolution == "1k"


def test_the_key_is_hidden_when_settings_are_printed():
    settings = Settings(_env_file=None, magic_hour_api_key=SecretStr(KEY))

    assert KEY not in repr(settings)
    assert KEY not in str(settings)


def test_the_time_limit_must_be_positive():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, magic_hour_timeout_seconds=0)


def test_the_key_never_reaches_the_logs(fake, make_service, caplog):
    caplog.set_level(logging.DEBUG)

    make_service().generate(REQUEST)  # a good run
    fake.create_reply = (401, {"message": "bad key"})
    with pytest.raises(ProviderAuthError):
        make_service().generate(REQUEST)  # a refused run

    assert KEY not in caplog.text
    assert "Bearer" not in caplog.text
