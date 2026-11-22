"""Makes a thumbnail picture with Magic Hour, saves it on disk and stores it in B2.

The service knows nothing about HTTP routes. It checks that storage works, starts
the job at Magic Hour, waits for it (with a time limit), downloads the picture,
checks that it really is an image, keeps it under a new name, and uploads it to
the private B2 bucket. The local copy always stays.

Why not the SDK's one-call `generate(wait_for_completion=True)`? Its wait loop
has no time limit, so a job stuck in the queue would hold a worker thread
forever. Here the steps are the SDK's own, called one by one: `create` starts the
job, `image_projects.get` checks it, and `download_files_sync` fetches the file.
"""

import base64
import json
import logging
import shutil
import threading
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

import httpx
import pydantic
from magic_hour import Client
from magic_hour.helpers import download_files_sync
from make_api_request import ApiError  # the error the SDK raises for a failed HTTP call
from PIL import Image

from app.core.config import get_settings
from app.schemas.thumbnail import ThumbnailImage, ThumbnailRequest, ThumbnailResponse
from app.services.b2_storage_service import B2StorageService, StoredObject, build_object_key, get_b2_storage_service
from app.services.errors import (
    ContentGenerationError,
    ImageGeneratedButNotStoredError,
    ImageNotCreatedError,
    ImageNotSavedError,
    InvalidModelOutputError,
    ProviderAuthError,
    ProviderRateLimitError,
    ProviderRequestError,
    ProviderTimeoutError,
    ProviderUnavailableError,
    StorageError,
)

logger = logging.getLogger(__name__)

# Fixed on purpose: a YouTube thumbnail is always 16:9, one picture per request.
ASPECT_RATIO = "16:9"
IMAGE_COUNT = 1
# The "tool" value from Magic Hour's own example.
STYLE_TOOL = "general"

HTTP_TIMEOUT_SECONDS = 30.0  # for each single call to Magic Hour
POLL_INTERVAL_SECONDS = 2.0
FINISHED_STATUSES = ("complete", "error", "canceled")

# The image formats we accept, and the file ending each one is saved with.
FILE_ENDINGS = {"PNG": "png", "JPEG": "jpg", "WEBP": "webp"}

# Sanity limits for a downloaded picture. They catch empty or placeholder files,
# not unusual but valid ones.
MIN_SIDE_PIXELS = 100
MAX_FILE_BYTES = 50 * 1024 * 1024

# Written next to a picture whose upload failed, so it can be uploaded later
# without paying for it again. A retry job can find these by the ending.
PENDING_UPLOAD_ENDING = ".pending-upload.json"


@dataclass(frozen=True)
class _SavedImage:
    """A checked picture that now sits in the output folder."""

    path: Path
    width: int
    height: int
    format: str  # png, jpeg or webp
    extension: str  # png, jpg or webp


def _preview_for(path: Path, content_type: str) -> str | None:
    """The picture as a data URL, so the page can show it at once.

    The bucket is private and there is no download link yet, so the picture itself
    travels in the answer. A stored thumbnail is not worth failing over a preview
    that cannot be read back, so that case just has no preview.
    """
    try:
        encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    except OSError as exc:
        logger.warning("Could not read the picture back for its preview: %s", type(exc).__name__)
        return None
    return f"data:{content_type};base64,{encoded}"


def _as_sentence(text: str) -> str:
    """End the text with a full stop unless it already ends like a sentence."""
    return text if text[-1] in ".!?" else text + "."


def build_prompt(request: ThumbnailRequest) -> str:
    """Turn the request into the sentence Magic Hour draws from.

    It uses all three things the user wrote: the video topic (also written on the
    picture), the description, and the global creative prompt. The creative prompt goes
    in as written. The rest is only about what to draw and how to keep the text readable,
    so it never fights the user's style.
    """
    parts = [f'A YouTube thumbnail for a video titled "{request.video_topic}".']
    if request.description:
        parts.append(f"About the video: {_as_sentence(request.description)}")
    if request.global_prompt:
        parts.append(f"Creative direction: {_as_sentence(request.global_prompt)}")
    parts.append(
        f'Write the title "{request.video_topic}" in huge, bold, high-contrast letters that are easy to read on a phone.'
    )
    parts.append("Keep the layout uncluttered, with one clear main subject. No other text, logos or watermarks.")
    return " ".join(parts)


def _to_service_error(exc: Exception) -> ContentGenerationError:
    """Turn a failure from the SDK or the network into one of our own errors."""
    if isinstance(exc, ApiError):
        # The status and body go to our log only. The error we return has fixed, safe text.
        logger.warning("Magic Hour answered with HTTP %s: %.300s", exc.status_code, exc.body)
        if exc.status_code in (401, 403):
            return ProviderAuthError()
        if exc.status_code == 429:
            return ProviderRateLimitError()
        if exc.status_code is not None and exc.status_code >= 500:
            return ProviderUnavailableError()
        return ProviderRequestError()

    # Checked before the general network error, which a timeout is a kind of.
    if isinstance(exc, httpx.TimeoutException):
        logger.warning("A call to Magic Hour timed out")
        return ProviderTimeoutError()
    if isinstance(exc, httpx.HTTPStatusError):
        # Only the file download raises this: Magic Hour gave a link that did not work.
        logger.warning("Downloading the picture failed with HTTP %s", exc.response.status_code)
        if exc.response.status_code >= 500:
            return ProviderUnavailableError()
        return InvalidModelOutputError()
    if isinstance(exc, httpx.HTTPError):
        logger.warning("Could not reach Magic Hour: %s", type(exc).__name__)
        return ProviderUnavailableError()

    # Anything else is a ValueError: the SDK could not read the reply. Either it was
    # not JSON at all (a proxy's error page, say), or it lacked fields the SDK needs.
    if isinstance(exc, pydantic.ValidationError):
        # Only field names and messages are logged, not the values.
        problems = [(error["loc"], error["msg"]) for error in exc.errors(include_input=False)]
        logger.warning("Magic Hour sent a reply that does not match the SDK's models: %s", problems)
    else:
        logger.warning("Magic Hour sent a reply that is not valid JSON")
    return InvalidModelOutputError()


def _read_image(path: Path) -> tuple[int, int, str]:
    """Open the file as a picture and return (width, height, format)."""
    if not path.is_file():
        logger.warning("The downloaded picture is missing from disk")
        raise InvalidModelOutputError()
    try:
        size = path.stat().st_size
        if size == 0 or size > MAX_FILE_BYTES:
            logger.warning("The downloaded file has an unusable size: %d bytes", size)
            raise InvalidModelOutputError()
        with Image.open(path) as image:
            image.load()  # reads every pixel, so a file cut off half way fails here
            width, height = image.size
            image_format = image.format
    except (OSError, SyntaxError, ValueError, Image.DecompressionBombError) as exc:
        logger.warning("The downloaded file is not a readable image")
        raise InvalidModelOutputError() from exc

    if image_format not in FILE_ENDINGS:
        logger.warning("The downloaded image has an unexpected format: %s", image_format)
        raise InvalidModelOutputError()
    if min(width, height) < MIN_SIDE_PIXELS:
        logger.warning("The downloaded image is too small for a thumbnail: %dx%d", width, height)
        raise InvalidModelOutputError()
    return width, height, image_format


class ThumbnailGenerationService:
    def __init__(
        self,
        client: Client,
        model: str,
        resolution: str,
        output_dir: Path,
        timeout_seconds: float,
        poll_interval_seconds: float = POLL_INTERVAL_SECONDS,
        *,
        storage: B2StorageService,
    ):
        # The clients are passed in (not built here) so tests can point them at
        # fakes, and the app reuses one client instead of making one per request.
        self._client = client
        self._storage = storage
        self._model = model
        self._resolution = resolution
        self._output_dir = output_dir
        self._timeout_seconds = timeout_seconds
        self._poll_interval_seconds = poll_interval_seconds

    def generate(self, request: ThumbnailRequest) -> ThumbnailResponse:
        """Make one thumbnail, or raise a ContentGenerationError or a StorageError."""
        # Our own name for the picture, so a new one can never replace an old one.
        image_id = uuid.uuid4().hex

        # Before paying for a picture, make sure there is somewhere to put it: B2
        # must answer, and the local folder must be writable. Storage is checked
        # first so a storage problem never leaves a folder behind.
        self._storage.check_ready()
        work_dir = self._prepare_work_dir(image_id)
        try:
            job_id = self._start_job(request, image_id)
            project = self._wait_until_finished(job_id)

            if project.status != "complete":
                # Magic Hour's code and message go to our log, not to the caller.
                logger.warning(
                    "Magic Hour ended image project %s as %s: %s", project.id, project.status, project.error
                )
                raise ImageNotCreatedError()

            saved = self._download_and_save(project.downloads, image_id, work_dir)
        finally:
            shutil.rmtree(work_dir, ignore_errors=True)

        stored = self._store(request, image_id, saved, project)
        return ThumbnailResponse(
            status=project.status,
            image=ThumbnailImage(
                reference=saved.path.name,
                width=saved.width,
                height=saved.height,
                format=saved.format,
                asset_id=image_id,
                object_key=stored.object_key,
                content_type=stored.content_type,
                size_bytes=stored.size_bytes,
                preview_data_url=_preview_for(saved.path, stored.content_type),
            ),
            provider_generation_id=project.id,
            credits_charged=project.credits_charged,
        )

    def _store(self, request: ThumbnailRequest, image_id: str, saved: _SavedImage, project) -> StoredObject:
        """Upload the checked picture. If that fails, keep it and say how to retry."""
        try:
            return self._storage.upload_image(saved.path, request.workspace_id, image_id, saved.extension)
        except Exception as exc:
            # The picture is paid for and valid, so it stays on disk.
            self._remember_failed_upload(request.workspace_id, image_id, saved, project, exc)
            if isinstance(exc, StorageError):
                raise ImageGeneratedButNotStoredError() from exc
            raise

    def _remember_failed_upload(self, workspace_id: int, image_id: str, saved: _SavedImage, project, exc) -> None:
        """Log the facts and write a small note next to the picture. Holds no secrets."""
        try:
            object_key = build_object_key(workspace_id, image_id, saved.extension)
        except ValueError:
            object_key = None
        note = {
            "asset_id": image_id,
            "workspace_id": workspace_id,
            "object_key": object_key,
            "local_file": saved.path.name,
            "width": saved.width,
            "height": saved.height,
            "format": saved.format,
            "provider_generation_id": project.id,
            "credits_charged": project.credits_charged,
            "failure": type(exc).__name__,
            "failed_at": datetime.now(timezone.utc).isoformat(),
        }
        # In the log too, in case the note cannot be written.
        logger.error("Thumbnail generated but not stored, kept locally for a retry: %s", json.dumps(note))

        note_path = self._output_dir / f"{image_id}{PENDING_UPLOAD_ENDING}"
        temporary = note_path.with_name(note_path.name + ".tmp")
        try:
            temporary.write_text(json.dumps(note, indent=2), encoding="utf-8")
            temporary.replace(note_path)  # the whole note or nothing, never half of it
        except OSError as write_error:
            logger.error("Could not write the retry note for %s: %s", image_id, write_error)
            temporary.unlink(missing_ok=True)

    def _start_job(self, request: ThumbnailRequest, image_id: str) -> str:
        try:
            created = self._client.v1.ai_image_generator.create(
                image_count=IMAGE_COUNT,
                style={"prompt": build_prompt(request), "tool": STYLE_TOOL},
                aspect_ratio=ASPECT_RATIO,
                model=self._model,
                resolution=self._resolution,
                name=f"PublishPro thumbnail {image_id[:8]}",
            )
        except (ApiError, httpx.HTTPError, ValueError) as exc:
            # Not retried: Magic Hour charges when the job is made, so a second try could cost twice.
            raise _to_service_error(exc) from exc
        return created.id

    def _wait_until_finished(self, job_id: str):
        """Check the job every few seconds until it ends, or the time limit passes."""
        deadline = time.monotonic() + self._timeout_seconds
        last_status = "unknown"
        while True:
            try:
                project = self._client.v1.image_projects.get(id=job_id)
                last_status = project.status
                if project.status in FINISHED_STATUSES:
                    return project
            except (ApiError, httpx.HTTPError, ValueError) as exc:
                error = _to_service_error(exc)
                # A hiccup while only checking is not worth losing a paid picture
                # for, so keep trying until the deadline. Any other failure is final.
                if not isinstance(error, ProviderUnavailableError):
                    raise error from exc

            if time.monotonic() >= deadline:
                logger.warning(
                    "Magic Hour image project %s was still %s after %.0f seconds",
                    job_id,
                    last_status,
                    self._timeout_seconds,
                )
                raise ProviderTimeoutError()
            time.sleep(self._poll_interval_seconds)

    def _prepare_work_dir(self, image_id: str) -> Path:
        """Make this picture's temporary folder, or fail before anything is charged."""
        # The SDK names the file after Magic Hour's link, and would overwrite one with
        # the same name. A fresh folder per picture keeps that from ever mattering.
        work_dir = self._output_dir / f".incoming-{image_id}"
        try:
            work_dir.mkdir(parents=True)
        except OSError as exc:
            logger.error("Cannot create a folder under %s: %s", self._output_dir, exc)
            raise ImageNotSavedError() from exc
        return work_dir

    def _download_and_save(self, downloads, image_id: str, work_dir: Path) -> _SavedImage:
        try:
            downloaded = download_files_sync(downloads=downloads, download_directory=str(work_dir))
        except httpx.HTTPError as exc:
            raise _to_service_error(exc) from exc
        except OSError as exc:
            logger.error("Could not write the downloaded picture to disk: %s", exc)
            raise ImageNotSavedError() from exc
        if not downloaded:
            logger.warning("Magic Hour finished the picture but listed nothing to download")
            raise InvalidModelOutputError()

        width, height, image_format = _read_image(Path(downloaded[0]))
        extension = FILE_ENDINGS[image_format]
        final_path = self._output_dir / f"{image_id}.{extension}"
        try:
            Path(downloaded[0]).replace(final_path)
        except OSError as exc:
            logger.error("Could not move the picture into %s: %s", self._output_dir, exc)
            raise ImageNotSavedError() from exc

        return _SavedImage(final_path, width, height, image_format.lower(), extension)


@lru_cache
def _build_service() -> ThumbnailGenerationService:
    settings = get_settings()
    key = settings.magic_hour_api_key
    if key is None or not key.get_secret_value().strip():
        logger.error("MAGIC_HOUR_API_KEY is not set")
        raise ProviderAuthError()

    # Storage is required too. If it is not set up this fails with a 503 before anything is paid for.
    storage = get_b2_storage_service()

    client = Client(token=key.get_secret_value().strip(), timeout=HTTP_TIMEOUT_SECONDS)
    return ThumbnailGenerationService(
        client,
        model=settings.magic_hour_image_model,
        resolution=settings.magic_hour_image_resolution,
        output_dir=settings.thumbnail_output_dir,
        timeout_seconds=settings.magic_hour_timeout_seconds,
        storage=storage,
    )


_build_lock = threading.Lock()


def get_thumbnail_generation_service() -> ThumbnailGenerationService:
    """Return the shared service, building it on the first call.

    The lock matters because routes run in a thread pool, and on a cold start
    every thread could otherwise build its own client.
    """
    with _build_lock:
        return _build_service()


# Tests reset the shared service through this.
get_thumbnail_generation_service.cache_clear = _build_service.cache_clear
