"""Builds the Gemini client that the text service uses.

Only text generation uses this. Pictures will get their own client later, so a
problem on one side can never touch the other.
"""

from google import genai
from google.genai import types


def build_gemini_client(api_key: str) -> genai.Client:
    """Make a Gemini client. The caller has already checked that the key is set."""
    return genai.Client(
        api_key=api_key,
        http_options=types.HttpOptions(
            # The SDK retries failed calls on its own, up to 4 times, and even
            # "attempts=1" still retries once. That would stack on top of our own
            # small retry, and a retry on a 429 only hammers a used-up quota.
            # Listing a status code that never happens (599) turns the SDK's
            # retries off, so only ours run.
            retry_options=types.HttpRetryOptions(attempts=1, http_status_codes=[599]),
        ),
    )
