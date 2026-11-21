"""Makes a thumbnail picture with Magic Hour and saves it on disk.

The service knows nothing about HTTP routes. It starts the job at Magic Hour, waits
for it (with a time limit), downloads the picture, checks that it really is an
image, and keeps it under a new name.

Why not the SDK's one-call `generate(wait_for_completion=True)`? Its wait loop
has no time limit, so a job stuck in the queue would hold a worker thread
forever. Here the steps are the SDK's own, called one by one: `create` starts the
job, `image_projects.get` checks it, and `download_files_sync` fetches the file.
"""

import logging
import shutil
import threading
import time
import uuid
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
from app.services.errors import (
    ContentGenerationError,
    ImageNotCreatedError,
    ImageNotSavedError,
    InvalidModelOutputError,
    ProviderAuthError,
    ProviderRateLimitError,
    ProviderRequestError,
    ProviderTimeoutError,
    ProviderUnavailableError,
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


def build_prompt(request: ThumbnailRequest) -> str:
    """Turn the request into the sentence Magic Hour draws from."""
    parts = [
        f"A YouTube thumbnail for a video about: {request.video_topic}.",
        f"Visual style: {request.visual_style}.",
        f'Write the headline "{request.heading}" in huge, bold, high-contrast letters that are easy to read on a phone.',
    ]
    if request.subtitle:
        parts.append(f'Add the smaller subtitle "{request.subtitle}" under the headline.')
    parts.append(
        "One clear main subject, saturated colors, dramatic lighting and an uncluttered layout. "
        "No other text, logos or watermarks."
    )
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
    ):
        # The client is passed in (not built here) so tests can point it at a
        # fake server, and the app reuses one client instead of making one per request.
        self._client = client
        self._model = model
        self._resolution = resolution
        self._output_dir = output_dir
        self._timeout_seconds = timeout_seconds
        self._poll_interval_seconds = poll_interval_seconds

    def generate(self, request: ThumbnailRequest) -> ThumbnailResponse:
        """Make one thumbnail, or raise a ContentGenerationError."""
        # Our own name for the picture, so a new one can never replace an old one.
        image_id = uuid.uuid4().hex

        # Before paying for a picture, make sure there is somewhere to put it.
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

            image = self._download_and_save(project.downloads, image_id, work_dir)
        finally:
            shutil.rmtree(work_dir, ignore_errors=True)

        return ThumbnailResponse(
            status=project.status,
            image=image,
            provider_generation_id=project.id,
            credits_charged=project.credits_charged,
        )

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

    def _download_and_save(self, downloads, image_id: str, work_dir: Path) -> ThumbnailImage:
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
        final_name = f"{image_id}.{FILE_ENDINGS[image_format]}"
        try:
            Path(downloaded[0]).replace(self._output_dir / final_name)
        except OSError as exc:
            logger.error("Could not move the picture into %s: %s", self._output_dir, exc)
            raise ImageNotSavedError() from exc

        return ThumbnailImage(reference=final_name, width=width, height=height, format=image_format.lower())


@lru_cache
def _build_service() -> ThumbnailGenerationService:
    settings = get_settings()
    key = settings.magic_hour_api_key
    if key is None or not key.get_secret_value().strip():
        logger.error("MAGIC_HOUR_API_KEY is not set")
        raise ProviderAuthError()

    client = Client(token=key.get_secret_value().strip(), timeout=HTTP_TIMEOUT_SECONDS)
    return ThumbnailGenerationService(
        client,
        model=settings.magic_hour_image_model,
        resolution=settings.magic_hour_image_resolution,
        output_dir=settings.thumbnail_output_dir,
        timeout_seconds=settings.magic_hour_timeout_seconds,
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
