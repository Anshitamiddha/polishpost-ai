"""Errors the content generation service can raise.

Each class means something different to the caller, so Phase 3 can turn them
into HTTP status codes with one `except` per class. The messages are fixed
text that is safe to show to end users: no provider details, no secrets. The
original provider error stays attached as `__cause__` and in the server logs.

Suggested HTTP mapping for Phase 3:

    ProviderAuthError         -> 502  (our key is wrong; alert us, not the user)
    ProviderRateLimitError    -> 429  (or 503)
    ProviderUnavailableError  -> 503
    ProviderRequestError      -> 502  (our request was refused; a bug on our side)
    InvalidModelOutputError   -> 502  (the model answered, but not with usable data)
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


class ProviderRequestError(ContentGenerationError):
    """The provider refused the request (bad request, unknown model, odd reply)."""

    default_message = "The AI service could not process the request."


class InvalidModelOutputError(ContentGenerationError):
    """The model replied, but the reply was not valid captions and hashtags."""

    default_message = "The AI service returned an unusable response."
