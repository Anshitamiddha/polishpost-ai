# PublishPro-AI service

A small FastAPI service. It writes captions, hashtags and SEO keywords with Gemini, and makes thumbnail pictures with Magic Hour. Only the Spring Boot backend should call it.

## Run

1. Copy `.env.example` to `.env` and add `AI_SERVICE_SHARED_SECRET`, `GEMINI_API_KEY` and `MAGIC_HOUR_API_KEY`.
2. Install dependencies: `pip install -r requirements.txt`.
3. Start it from the `python-ai-service` folder, because `.env` is read from the folder you start in: `uvicorn app.main:app --reload`.

Every generation endpoint needs the `X-Internal-Service-Token` header. Provider keys stay in this service and are never sent back.

## Endpoints

- `POST /api/v1/publish/text` writes captions, hashtags and primary/secondary SEO keywords with Gemini.
- `POST /api/v1/content/generate` is the older caption endpoint. It stays for backwards compatibility.
- `POST /api/v1/publish/thumbnails` makes one 16:9 thumbnail with Magic Hour.

## Thumbnails

Send `video_topic`, `heading`, `visual_style` and, if you want, `subtitle`. The service waits for Magic Hour to finish (at most 120 seconds, set by `MAGIC_HOUR_TIMEOUT_SECONDS`), downloads the picture, checks that it is a real PNG, JPEG or WEBP file (at least 100 pixels on its short side, at most 50 MB), and saves it in `generated/thumbnails/` under a new name, so an old picture is never replaced.

The answer holds `success`, `status`, `image` (`reference`, `width`, `height`, `format`), `provider_generation_id` and `credits_charged`. `reference` is only a file name. The answer never contains a path or a link. Saving the picture somewhere permanent is a later step.

Before it asks Magic Hour for anything, the service makes sure it can write to the output folder, so a disk problem costs no credits. If the disk fails later, the answer is a 500 with "The thumbnail could not be saved on the server."

The model and size can be changed with `MAGIC_HOUR_IMAGE_MODEL` (default `z-image-turbo`) and `MAGIC_HOUR_IMAGE_RESOLUTION` (default `640px`). Magic Hour charges credits for every picture, so keep the small size while testing.

## Backblaze B2 (connection check only)

The service can connect to a private Backblaze B2 bucket through its S3-compatible API, using `boto3`. Nothing is stored there yet. There is no upload, download or storage endpoint.

Put `B2_KEY_ID`, `B2_APPLICATION_KEY`, `B2_BUCKET_NAME`, `B2_ENDPOINT_URL` and `B2_REGION` in `.env`. The endpoint is the S3 endpoint Backblaze shows for the bucket, such as `https://s3.us-west-004.backblazeb2.com`, and the region is the part inside it, such as `us-west-004`. Then check the connection from the `python-ai-service` folder:

```
python -m app.services.b2_connection_check
```

It makes one `HeadBucket` call, which only asks whether the bucket is reachable with these credentials. It prints PASS or FAIL, never prints the keys, and uploads and changes nothing.

## Content intelligence (in progress)

`app/ml/content_intelligence/` is a workspace for learning from a YouTube metadata dataset. So far it holds one script that reads a CSV file and reports what is in it. Nothing here is used by the API yet.

Put the downloaded CSV files in `app/ml/content_intelligence/datasets/raw/`. A zip must be extracted first. Then run this from the `python-ai-service` folder:

```
python app/ml/content_intelligence/preprocessing/inspect_dataset.py
```

With no path it uses the only CSV in `raw/`. If `raw/` holds several CSV files, name the one you want:

```
python app/ml/content_intelligence/preprocessing/inspect_dataset.py app/ml/content_intelligence/datasets/raw/CAvideos.csv
```

The report covers size, columns and types, the first five records, missing values, duplicate rows and categories. It also checks for descriptions, real tags, hashtags and view, like and comment counts. It only reads the file and changes nothing. It needs `pandas`, which is not in `requirements.txt` yet.
