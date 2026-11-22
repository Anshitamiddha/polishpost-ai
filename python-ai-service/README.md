# PublishPro-AI service

A small FastAPI service that makes thumbnail pictures with Magic Hour and keeps them in a private Backblaze B2 bucket. Only the Spring Boot backend should call it.

## Run

1. Copy `.env.example` to `.env` and add `AI_SERVICE_SHARED_SECRET`, `MAGIC_HOUR_API_KEY` and the five `B2_` settings (see the Backblaze section).
2. Install dependencies: `pip install -r requirements.txt`.
3. Start it from the `python-ai-service` folder, because `.env` is read from the folder you start in: `uvicorn app.main:app --reload`.

Every generation endpoint needs the `X-Internal-Service-Token` header. Provider keys stay in this service and are never sent back.

## Endpoints

- `GET /api/v1/health` says the service is running. It needs no token.
- `POST /api/v1/publish/thumbnails` makes one 16:9 thumbnail with Magic Hour and stores it in B2.

## Thumbnails

Send `workspace_id`, `video_topic` and, if you want, `description` and `global_prompt`. These four names are the same in React, Spring Boot and this service. Any other field, including the old `heading`, `subtitle`, `visual_style`, `title` and `prompt`, is refused with a 422.

- `video_topic` is the video's title (3 to 60 characters). It is also the text written on the picture.
- `description` is what the video is about (up to 300 characters).
- `global_prompt` is the user's own creative direction (up to 500 characters), the "global creative prompt" from the Create Post page.

The Magic Hour prompt uses all three: it names the video by its `video_topic`, adds the `description` as "About the video", adds the `global_prompt` as "Creative direction", and asks for the `video_topic` to be written on the picture. The `global_prompt` goes in exactly as written, so the service adds no style of its own that could fight it. For example, a topic of "AI APP IN 7 DAYS", a description of "I built a full AI app in seven days" and the page's default prompt become:

> A YouTube thumbnail for a video titled "AI APP IN 7 DAYS". About the video: I built a full AI app in seven days. Creative direction: Create a bold, cinematic YouTube thumbnail. Keep the creator as the main focus, use dramatic lighting, strong contrast, and leave space for a short headline. Write the title "AI APP IN 7 DAYS" in huge, bold, high-contrast letters that are easy to read on a phone. Keep the layout uncluttered, with one clear main subject. No other text, logos or watermarks.

A missing `description` or `global_prompt` just leaves its sentence out. The service always makes exactly one picture: the request has no field for a number of pictures, and it always asks Magic Hour for `image_count` 1.

The React page does not call this service. It goes through the Spring Boot backend, which checks the workspace and then sends the same field names on. Spring must call this service over plain HTTP/1.1. Java's default asks plain-http servers to upgrade to HTTP/2, and uvicorn then loses the request body (a 422 "body: Field required"), answers "Invalid HTTP request received" or resets the connection.

`workspace_id` is a whole number above zero. Only the Spring Boot backend may set it, and only after it has checked that the user belongs to that workspace. This service has no database, so it trusts the value because the caller proved who it is with `X-Internal-Service-Token`. It is read from the request body and nowhere else. The browser must never send it straight to this service.

What happens, in order:

1. The service checks that B2 answers and that it can write to the output folder. If not, it stops here and nothing is charged.
2. It asks Magic Hour for the picture and waits (at most 120 seconds, set by `MAGIC_HOUR_TIMEOUT_SECONDS`).
3. It downloads the picture and checks that it is a real PNG, JPEG or WEBP file (at least 100 pixels on its short side, at most 50 MB). A bad picture is never uploaded.
4. It saves the picture in `generated/thumbnails/` under a new name. This local copy always stays.
5. It uploads the same file to B2 as `workspaces/{workspace_id}/generated/{asset_id}.{ending}`, for example `workspaces/12/generated/3f9c0a7e5b1d4c2e8a6f0b9d7c5e3a1f.png`. The `asset_id` is a new random ID for every picture, so nothing is ever overwritten.

The answer holds `success`, `status`, `image`, `provider_generation_id` and `credits_charged`. `image` has `reference` (the local file name), `width`, `height`, `format`, `asset_id`, `object_key` (where it is in B2), `content_type`, `size_bytes` and `preview_data_url`. `preview_data_url` is the picture itself as a data URL, so the page can show it right away without a link to the private bucket. It is empty only if the saved file could not be read back. The answer never contains a path, a link or the bucket name, and there are no downloads or presigned links yet.

If something fails, the answer says which side failed:

- **Storage not ready (503):** nothing was generated or charged, for example "File storage is temporarily unavailable. Please try again."
- **Magic Hour failed:** the same answers as before (429, 502, 503), and nothing is uploaded.
- **Generated but not stored (503, or 502 if B2 refused the upload):** "The thumbnail was generated, but it could not be stored. The image was kept on the server, so it does not need to be generated again." The credits were spent, so do not ask for the same picture again.
- **Disk problem (500):** "The thumbnail could not be saved on the server."

When an upload fails after the picture was made, the service keeps the picture and writes a small note next to it, `{asset_id}.pending-upload.json`. It holds the asset ID, workspace ID, the key it should have gone to, the local file name, Magic Hour's generation ID and when it failed. It holds no keys or secrets. The same facts go to the server log. A later step can use these to upload the picture without paying for it again. That step is not built yet.

The model and size can be changed with `MAGIC_HOUR_IMAGE_MODEL` (default `z-image-turbo`) and `MAGIC_HOUR_IMAGE_RESOLUTION` (default `640px`). Magic Hour charges credits for every picture, so keep the small size while testing.

## Backblaze B2

The service uses a private Backblaze B2 bucket through its S3-compatible API, using `boto3`. It only uploads the generated thumbnails. There is no download, listing or delete, and no storage endpoint. B2 is required: without these settings the thumbnail endpoint answers 503 before anything is charged.

The upload key needs permission to write files in the bucket.

Put `B2_KEY_ID`, `B2_APPLICATION_KEY`, `B2_BUCKET_NAME`, `B2_ENDPOINT_URL` and `B2_REGION` in `.env`. The endpoint is the S3 endpoint Backblaze shows for the bucket, such as `https://s3.us-west-004.backblazeb2.com`, and the region is the part inside it, such as `us-west-004`. Then check the connection from the `python-ai-service` folder:

```
python -m app.services.b2_connection_check
```

It makes one `HeadBucket` call, which only asks whether the bucket is reachable with these credentials. It prints PASS or FAIL, never prints the keys, and uploads and changes nothing. A passing check does not prove the key may write files. That only shows when a picture is uploaded.

The client asks boto3 for checksums only when S3 requires them (`request_checksum_calculation` and `response_checksum_validation` are `when_required`). Without that, newer boto3 versions add a trailing checksum that Backblaze's S3 API has rejected.
