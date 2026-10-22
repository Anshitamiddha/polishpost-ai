
from openai import OpenAI

from app.core.config import get_settings


def main():
    settings = get_settings()

    if not settings.groq_api_key:
        raise RuntimeError("GROQ_API_KEY is not configured.")

    client = OpenAI(
        api_key=settings.groq_api_key.get_secret_value(),
        base_url="https://api.groq.com/openai/v1",
        timeout=30.0,
        max_retries=2,
    )

    try:
        print("Sending request to Groq...", flush=True)

        response = client.responses.create(
            model="openai/gpt-oss-20b",
            input=(
                "Write one engaging YouTube caption about "
                "learning Python programming. Keep it under 30 words."
            ),
        )

        print("\nGenerated caption:\n")
        print(response.output_text)

    except Exception as exc:
        print(f"Groq request failed: {type(exc).__name__}: {exc}")

    finally:
        client.close()


if __name__ == "__main__":
    main()
