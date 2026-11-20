# PublishPro-AI service-layer implementation

## Delivered

- Added `POST /api/v1/publish/text` for Gemini-generated captions, focused hashtags and primary/secondary SEO keywords.
- Added `POST /api/v1/publish/thumbnails` for 2–3 xAI Grok 16:9 thumbnail variations, with global visual prompt, optional references, color, composition and mood preferences.
- Added a high-click YouTube thumbnail preset: bold short headline, expressive focal subject, saturated contrast, dramatic lighting and uncluttered visual hierarchy.
- Added `POST /api/v1/publish/thumbnails/edit` for a single, non-destructive thumbnail edit using a local prompt.
- Added strict Pydantic request/response contracts, including unique input keywords, bounded variation count, base64 image validation and image-signature checks for PNG/JPEG/WEBP.
- Maintained Gemini and xAI Grok as independent provider services with distinct credentials and client construction.
- Preserved the existing content endpoint and its tests for compatibility.

## Prompt and versioning behavior

Initial thumbnails use only the global prompt and generation preferences. Editing takes the selected original image plus a local edit instruction. The original global prompt is included only as immutable style context; it is never changed or used as the local instruction. Each edit asks the provider for a new asset and returns it separately, leaving persistence/version tracking to the caller's storage layer.

## Security and boundaries

- Provider credentials remain server-side environment settings.
- All generation routes require `X-Internal-Service-Token`.
- The service does not add database, file storage or persistence responsibilities.
- Provider failures are mapped to safe HTTP errors without exposing keys or provider details.

## Verification

Ran `pytest -q`: **283 passed**.
Ran Python bytecode compilation for `app/`: **passed**.

## Provider naming note

The supplied configuration uses `XAI_API_KEY` and `grok-imagine-image-2.0`, so the image implementation targets **xAI Grok**. The user wording said “Groq”; Groq is a separate inference provider and does not provide this image-generation endpoint.
