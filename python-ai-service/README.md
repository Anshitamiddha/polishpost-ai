# PublishPro-AI Python AI Service

This is the small service that does the AI work for PublishPro-AI. Right now it writes **captions and hashtags** for a video. Later it will also make images.

It is built with FastAPI (Python). The Spring Boot backend will be the one to call it. Browsers and the React app will never talk to it directly, because it holds the AI keys.

## What it does today

You send it a video topic. It sends back ready-to-use captions and hashtags.

- It asks Groq (the AI provider) to write the text, using the `openai/gpt-oss-20b` model.
- It checks everything Groq says before passing it on. Broken answers are turned into an error, never passed along as if they were fine.
- It has a health check and a built-in page (`/docs`) where you can try it by hand.

It does **not** have login yet, and it is **not** connected to Spring Boot or React yet.

## How a request travels

1. Someone sends `POST /api/v1/content/generate` with a topic.
2. FastAPI checks the request against the rules in `schemas/generation.py`. If something is wrong, it answers `422` and stops.
3. The route (`api/routes/content.py`) hands the request to the service. The route itself does no AI work.
4. The service (`services/content_generation_service.py`) builds the instructions, asks Groq, and waits.
5. The service checks Groq's answer, tidies the hashtags, and checks it against the response rules.
6. The route sends back `captions` and `hashtags`. If anything failed on the way, it sends an error instead.

## What has been built so far

| Step | What it added |
|---|---|
| Skeleton | The FastAPI app, `GET /api/v1/health`, and settings that read `.env` |
| Phase 1 | The rules for the request and the response (`schemas/generation.py`) |
| Phase 2 | The service that talks to Groq and checks the answer (`services/`) |
| Phase 3 | The endpoint `POST /api/v1/content/generate` and the error codes |

## What you need

- Python 3.11 or newer (built and tested with 3.13)
- Windows PowerShell (the commands below), or any shell with small changes

## Set it up

Run these from the `python-ai-service` folder.

```powershell
cd python-ai-service

# 1. Create a virtual environment (a private folder of packages for this service)
python -m venv .venv

# 2. Turn it on. Your prompt will start with (.venv)
.\.venv\Scripts\Activate.ps1

# 3. Install the packages
pip install -r requirements.txt

# 4. Create your own settings file (Git ignores it)
copy .env.example .env
```

Then open `.env` and add your Groq key as `GROQ_API_KEY=...`. Keep it only in `.env`. Never paste it into code or chat.

If step 2 says "running scripts is disabled on this system", allow scripts for this PowerShell window only, then try again:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

You can also skip step 2 and call the environment's Python directly, for example `.\.venv\Scripts\python.exe -m pytest`.

## Start the server

```powershell
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

- `--host 127.0.0.1` means only your own computer can reach it. Keep it that way for now, because there is no login yet.
- `--reload` restarts the server when you edit code. Leave it out outside development.
- Stop the server with `Ctrl+C`.

## Run the tests

```powershell
pytest
```

All tests use fakes. They never call Groq, so they cost nothing and need no internet or key.

## Try it out

### In your browser (easiest)

1. Start the server.
2. Open <http://127.0.0.1:8000/docs>.
3. Click `POST /api/v1/content/generate`, then **Try it out**.
4. Change the example, then click **Execute**. The answer appears below.

### From PowerShell

```powershell
$body = @{ video_topic = "Sunrise hike in the Alps"; tone = "inspiring"; keywords = @("hiking", "alps") } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/v1/content/generate -ContentType "application/json" -Body $body
```

Heads-up: Windows PowerShell 5.1 may show emoji and long dashes as garbage characters (like `â` or `ð`). The service sends them correctly. PowerShell 5.1 just reads them wrongly. The `/docs` page shows them properly.

To check the service is alive:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/v1/health
```

## What to send

`POST /api/v1/content/generate` takes JSON:

| Field | Needed? | If you leave it out | Rules |
|---|---|---|---|
| `video_topic` | Yes | | What the video is about. 1 to 500 characters. Spaces around it are trimmed, so a blank topic counts as empty. |
| `tone` | No | `"engaging"` | The voice, like `"funny"` or `"professional"`. Up to 50 characters. |
| `keywords` | No | none | Words to work in. Up to 10, each up to 50 characters. |
| `language` | No | `"English"` | The language for the captions. Up to 50 characters. |

If you send a field the service does not know (for example `keyword` instead of `keywords`), it answers with an error. It does not quietly ignore it.

## What you get back

```json
{
  "captions": [
    "Morning light paints the Alps, rise with the trail and let every step inspire you",
    "Who needs a sunrise alarm when you have the mountains? Start your day on the ridge!",
    "Feel the world awaken beneath your boots."
  ],
  "hashtags": ["#hiking", "#alps", "#sunrise", "#inspire", "#mountains"]
}
```

(Shortened from a real answer. You normally get 3 captions and about 10 hashtags.)

- Captions are written to take different angles, not the same sentence reworded.
- Hashtags always start with `#` and have no spaces or repeats.
- The AI is told not to invent facts about your video. It only knows the topic and keywords you give it.

## When something goes wrong

A failure is never sent back as a normal `200` answer. You get an error code and a short message like `{"detail": "..."}`. The message never contains keys or internal details.

| You see | What it means | What to do |
|---|---|---|
| `422` | Something is wrong with what you sent. The message names the field. | Fix the request. |
| `429` | Groq says its limit is used up for now. | Wait a little, then try again. |
| `502` | Groq answered, but not with something usable (for example a broken hashtag). | Try again. If it keeps happening, look at the server log. |
| `503` | The key is missing or wrong, or Groq is down or too slow. | Check `GROQ_API_KEY` in `.env` and your internet, then try again. |
| `500` | A bug on our side. | Look at the server log. |

The server log is the terminal window where the server is running. That is where the full details go, so they never reach the person who made the request.

Groq problems that might clear up on their own (a timeout, a network hiccup, Groq being down for a moment) are retried up to 2 more times. Problems that will not fix themselves are not retried: a wrong key, a bad request, or a used-up limit.

## Settings

Settings come from environment variables. For local work, put them in the `.env` file in this folder. Real environment variables win over the file.

| Setting | Needed? | What it is |
|---|---|---|
| `GROQ_API_KEY` | Yes, for captions and hashtags | Your Groq key. Without it the endpoint answers `503`. |
| `GROQ_MODEL` | No | Defaults to `openai/gpt-oss-20b` |
| `GROQ_BASE_URL` | No | Defaults to `https://api.groq.com/openai/v1` |
| `APP_NAME` | No | The name shown in `/docs` and the health check |
| `APP_VERSION` | No | The version shown in `/docs` and the health check |
| `GEMINI_API_KEY` | Not used yet | Saved for the image feature later |

Never commit a real `.env`, and never send AI keys to the React frontend. They belong only to this service.

## What is where

```
python-ai-service/
|-- app/
|   |-- main.py                 creates the app and plugs in the routes under /api/v1
|   |-- api/routes/health.py    GET /api/v1/health
|   |-- api/routes/content.py   POST /api/v1/content/generate, and which error becomes which code
|   |-- core/config.py          reads the settings (env vars and .env)
|   |-- schemas/generation.py   the rules for the request and the response
|   `-- services/
|       |-- content_generation_service.py  asks Groq and checks the answer
|       `-- errors.py           the few kinds of error the service can raise
|-- tests/
|   |-- test_health.py                        health check and docs page
|   |-- test_generation_schemas.py            the request and response rules
|   |-- test_content_generation_service.py    the Groq service (Groq is faked)
|   `-- test_content_api.py                   the endpoint (Groq is faked)
|-- test_groq_text.py           a manual check that your Groq key works (makes one real call)
|-- pytest.ini                  lets `pytest` find the `app` folder
|-- requirements.txt            the exact package versions
|-- .env.example                a safe template for your settings
`-- .gitignore                  keeps .venv, .env and caches out of Git
```

## Ground rules

- **No database here.** This service never touches PostgreSQL. Spring Boot owns the data.
- **No login here yet.** Login between Spring Boot and this service comes in a later step, before anything but your own computer can reach it.
- **Text only for now.** Images and thumbnails come later and will be kept separate from the text part.

## What is next

Not built yet: connecting Spring Boot to this endpoint, login between the two services, and image generation with Gemini.
