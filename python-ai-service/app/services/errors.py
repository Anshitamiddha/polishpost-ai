"""Errors the thumbnail generation service can raise.

Each class means something different to the caller, so the routes can turn them
into HTTP status codes with one lookup per class. The messages are fixed
text that is safe to show to end users: no provider details, no secrets. The
original provider error stays attached as `__cause__` and in the server logs.

The HTTP mapping lives in app/api/errors.py (STATUS_FOR_ERROR):

    ProviderAuthError         -> 503  (our key is missing or wrong; alert us, not the user)
    ProviderRateLimitError    -> 429
    ProviderUnavailableError  -> 503
    ProviderTimeoutError      -> 503  (a kind of ProviderUnavailableError)
    ProviderRequestError      -> 502  (our request was refused; a bug on our side)
    InvalidModelOutputError   -> 502  (the model answered, but not with usable data)
    ImageNotCreatedError      -> 502  (the image model made no picture; the user can retry)
    ImageNotSavedError        -> 500  (our own disk refused the file; found before Magic Hour is paid)

File storage (Backblaze B2) has its own family, StorageError, kept apart from the
generation errors above so a caller can tell "no picture was made" from "a
picture was made but could not be stored":

    StorageNotConfiguredError -> 503  (B2 settings missing, or pointing at the wrong bucket or endpoint)
    StorageAuthError          -> 503  (B2 refused our key or its permissions; alert us)
    StorageUnavailableError   -> 503  (timeouts, network trouble, B2 outage)
    StorageTimeoutError       -> 503  (a kind of StorageUnavailableError)
    StorageRequestError       -> 502  (B2 refused the upload itself)
    StorageFileError          -> 500  (the local file to upload is missing or unusable)
    ImageGeneratedButNotStoredError -> the status of the storage problem behind it
"""


class ContentGenerationError(Exception):
    """Base class: catch this to handle any generation failure."""

    default_message = "Content generation failed."

    def __init__(self, message: str | None = None):
        # Callers raise these with no arguments so the text stays the safe default.
        super().__init__(message or self.default_message)


class ProviderAuthError(ContentGenerationError):
    """The API key is missing or the provider rejected it."""

    default_message = "The AI service is not configured correctly."


class ProviderRateLimitError(ContentGenerationError):
    """The provider's rate limit or quota is used up."""

    default_message = "The AI service is busy right now. Please try again later."


class ProviderUnavailableError(ContentGenerationError):
    """Timeout, network failure or provider outage (still failing after retries)."""

    default_message = "The AI service is temporarily unavailable. Please try again."


class ProviderTimeoutError(ProviderUnavailableError):
    """The provider took too long. It stays a 503, but image calls are not retried."""

    # A slow image call may still be billed, so a second try could cost twice.
    default_message = "The AI service took too long to answer. Please try again."


class ProviderRequestError(ContentGenerationError):
    """The provider refused the request (bad request, unknown model, odd reply)."""

    default_message = "The AI service could not process the request."


class InvalidModelOutputError(ContentGenerationError):
    """The provider replied, but the reply was not usable (an unreadable answer or a bad file)."""

    default_message = "The AI service returned an unusable response."


class ImageNotCreatedError(ContentGenerationError):
    """The image model answered without a picture (often a safety refusal)."""

    # Unlike the other messages this one is advice for the person, since they
    # can fix it by changing the prompt.
    default_message = "The AI could not create a thumbnail from this request. Try a different prompt."


class ImageNotSavedError(ContentGenerationError):
    """The picture could not be written to this server's disk (permissions, a full disk)."""

    # Our own disk is at fault, not the caller, so the text says so plainly.
    default_message = "The thumbnail could not be saved on the server."


class StorageError(Exception):
    """Base class for file storage failures. Not a ContentGenerationError on purpose."""

    default_message = "File storage failed."

    def __init__(self, message: str | None = None):
        # Raised with no arguments so the text stays the safe default.
        super().__init__(message or self.default_message)


class StorageNotConfiguredError(StorageError):
    """A B2 setting is missing, or the bucket, endpoint or region is wrong."""

    default_message = "File storage is not configured correctly."


class StorageAuthError(StorageError):
    """B2 refused our key, or the key may not use this bucket."""

    default_message = "File storage refused the server's credentials or permissions."


class StorageUnavailableError(StorageError):
    """Timeout, network failure or a B2 outage."""

    default_message = "File storage is temporarily unavailable. Please try again."


class StorageTimeoutError(StorageUnavailableError):
    """B2 took too long. It stays a 503, like any other outage."""

    default_message = "File storage took too long to answer. Please try again."


class StorageRequestError(StorageError):
    """B2 answered, but refused the upload itself."""

    default_message = "File storage could not accept the upload."


class StorageFileError(StorageError):
    """The local file to upload is missing, empty or too large."""

    default_message = "The image file to store is missing or unusable."


class ImageGeneratedButNotStoredError(StorageError):
    """The picture was made and paid for, but storing it failed."""

    # Says so plainly: the caller must not generate it again and pay twice.
    default_message = (
        "The thumbnail was generated, but it could not be stored. "
        "The image was kept on the server, so it does not need to be generated again."
    )
