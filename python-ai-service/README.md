# PublishPro-AI Python AI Service

A small FastAPI service that will do the AI work for PublishPro-AI (captions, hashtags, thumbnails, and so on). The Spring Boot backend will call it. Browsers will not.

**Current state: a skeleton plus a Groq caption/hashtag service.** It starts, answers a health check, and serves API docs. The generation service exists in code and is tested, but no HTTP endpoint exposes it yet, and the service is not connected to the Spring Boot backend yet.

## Requirements

- Python 3.11 or newer (developed and tested with 3.13)
- Windows PowerShell (commands below), or any shell with small changes

## Setup

Run these from the `python-ai-service` folder.

```powershell
cd python-ai-service

# 1. Create a virtual environment (a private folder of packages for this service)
python -m venv .venv

# 2. Activate it. Your prompt will start with (.venv)
.\.venv\Scripts\Activate.ps1

# 3. Install the dependencies
pip install -r requirements.txt

# 4. Optional: create your local settings file (it is ignored by Git)
copy .env.example .env
```

If step 2 says "running scripts is disabled on this system", allow scripts for this PowerShell window only and try again:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

You can also skip activation and call the environment's Python directly, for example `.\.venv\Scripts\python.exe -m pytest`.

## Run

```powershell
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

- `--host 127.0.0.1` keeps the service reachable only from your own computer. Keep it that way: this service is internal.
- `--reload` restarts the server when you edit code. Leave it out outside development.
- Stop the server with `Ctrl+C`.

## Test

```powershell
pytest
```

## Endpoints

| Method and path | What it does |
|---|---|
| `GET /api/v1/health` | Returns `{"status": "ok", "service": "...", "version": "..."}` when the service is running |
| `GET /docs` | Interactive API docs (Swagger UI) |
| `GET /redoc` | Alternative API docs |
| `GET /openapi.json` | The machine-readable API description |

Everything real lives under `/api/v1/` so a future `/api/v2/` can sit next to it.

Quick check:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/v1/health
```

## Configuration

Settings are read from environment variables. For local work you can put them in a `.env` file in this folder (copy `.env.example`). Real environment variables win over the file.

| Variable | Used now? | Meaning |
|---|---|---|
| `APP_NAME` | Yes, optional | Service name shown in `/docs` and in the health response |
| `APP_VERSION` | Yes, optional | Version shown in `/docs` and in the health response |
| `GROQ_API_KEY` | Yes, required for caption/hashtag generation | Groq API key. Without it the service raises `ProviderAuthError` when asked to generate. |
| `GROQ_MODEL` | Yes, optional | Defaults to `openai/gpt-oss-20b` |
| `GROQ_BASE_URL` | Yes, optional | Defaults to `https://api.groq.com/openai/v1` |
| `GEMINI_API_KEY` | No | Reserved for the later image-generation step. |

Never commit a real `.env`, and never send AI keys to the React frontend. They belong only to this service.

## Project layout

```
python-ai-service/
|-- app/
|   |-- main.py                 creates the FastAPI app and registers routers under /api/v1
|   |-- api/routes/health.py    GET /api/v1/health
|   |-- core/config.py          Settings class (Pydantic Settings, reads env vars / .env)
|   |-- schemas/generation.py   GenerationRequest / GenerationResponse (caption + hashtag contract)
|   `-- services/
|       |-- content_generation_service.py  asks Groq for captions + hashtags and checks the answer (no route yet)
|       `-- errors.py           the few errors the service raises (Phase 3 maps them to HTTP codes)
|-- tests/test_health.py        tests for the health endpoint and docs
|-- tests/test_generation_schemas.py  tests for the generation request/response models
|-- tests/test_content_generation_service.py  tests for the Groq service (Groq is faked, no real calls)
|-- test_groq_text.py           standalone manual check that your Groq key works (makes a real call)
|-- pytest.ini                  lets `pytest` find the `app` package
|-- requirements.txt            exact pinned dependencies
|-- .env.example                placeholder settings (safe to commit)
`-- .gitignore                  keeps .venv, .env, caches out of Git
```

## Boundaries

- No database access. The service never talks to PostgreSQL. The Spring Boot backend owns the data.
- No login or user handling here yet. Authentication between Spring Boot and this service will be added in a later step, before it is reachable by anything other than your own machine.
- Caption and hashtag generation exists as a service (Groq) but has no HTTP endpoint yet. No thumbnail or image code yet.
