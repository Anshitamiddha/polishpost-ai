
from google import genai

from app.core.config import get_settings


def main():
    settings = get_settings()

    if not settings.gemini_api_key:
        raise RuntimeError("GEMINI_API_KEY is not configured.")

    client = genai.Client(
        api_key=settings.gemini_api_key.get_secret_value()
    )

    try:
        interaction = client.interactions.create(
            model="gemini-3.7-flash",
            input=(
                "Write one engaging YouTube caption about "
                "learning Python programming. Keep it under 30 words."
            ),
        )

        result = interaction.output_text

        if not result:
            print("Gemini returned no text.")
            return

        print("\nGemini text-generation succeeded:\n")
        print(result)

    finally:
        client.close()


if __name__ == "__main__":
    main()
