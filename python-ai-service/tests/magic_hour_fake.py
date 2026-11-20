"""A fake Magic Hour for tests.

The real Magic Hour SDK talks to this small local web server, so the real HTTP,
polling and download code runs, offline and free. It plays the three things the
service uses: starting a job, checking a job, and downloading the picture file.
"""

import http.server
import json
import threading
import time
from io import BytesIO

from PIL import Image


def image_bytes(image_format: str = "PNG", size: tuple[int, int] = (640, 360)) -> bytes:
    """A real picture file of the given format, made by Pillow."""
    buffer = BytesIO()
    Image.new("RGB", size, (200, 40, 60)).save(buffer, format=image_format)
    return buffer.getvalue()


class FakeMagicHour:
    """Replies are scripted by setting attributes; each request is recorded."""

    def __init__(self):
        self.requests: list[dict] = []
        self.create_reply: tuple[int, object] = (200, {"credits_charged": 5, "frame_cost": 5, "id": "job-1"})
        # One reply per check of the job, in order. The last one repeats.
        self.poll_replies: list[tuple[int, object]] = []
        self.file_reply: tuple[int, bytes] = (200, image_bytes())
        self.create_delay_seconds = 0.0
        outer = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def _record(self, body=None):
                outer.requests.append(
                    {
                        "method": self.command,
                        "path": self.path,
                        "headers": {k.lower(): v for k, v in self.headers.items()},
                        "body": body,
                    }
                )

            def _send(self, status, payload, content_type="application/json"):
                raw = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
                self.send_response(status)
                self.send_header("content-type", content_type)
                self.send_header("content-length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

            def do_POST(self):
                length = int(self.headers.get("content-length", 0))
                self._record(json.loads(self.rfile.read(length) or b"null"))
                time.sleep(outer.create_delay_seconds)
                if self.path == "/v1/ai-image-generator":
                    self._send(*outer.create_reply)
                else:
                    self._send(404, {"message": "not found"})

            def do_GET(self):
                self._record()
                if self.path.startswith("/v1/image-projects/"):
                    polls_so_far = sum(1 for r in outer.requests if r["path"].startswith("/v1/image-projects/"))
                    replies = outer.poll_replies
                    self._send(*replies[min(polls_so_far, len(replies)) - 1])
                elif self.path.startswith("/files/"):
                    status, content = outer.file_reply
                    self._send(status, content, content_type="image/png")
                else:
                    self._send(404, {"message": "not found"})

            def log_message(self, *args):  # keep the test output quiet
                pass

        self._server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self._thread = threading.Thread(target=lambda: self._server.serve_forever(poll_interval=0.01), daemon=True)

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self._server.server_address[1]}"

    def project(self, status: str = "complete", *, downloads=None, error=None) -> tuple[int, dict]:
        """A reply to "how is my job doing?" in the shape the SDK expects."""
        if downloads is None:
            downloads = [{"url": f"{self.url}/files/picture.png", "expires_at": "2026-11-18T12:00:00Z"}]
        return 200, {
            "created_at": "2026-11-18T10:00:00Z",
            "credits_charged": 5,
            "downloads": downloads if status == "complete" else [],
            "enabled": True,
            "error": error,
            "id": "job-1",
            "image_count": 1,
            "name": "PublishPro thumbnail",
            "status": status,
            "total_frame_cost": 5,
            "type": "AI_IMAGE",
        }

    def start(self) -> "FakeMagicHour":
        self.poll_replies = [self.project("complete")]
        self._thread.start()
        return self

    def stop(self) -> None:
        self._server.shutdown()
        self._server.server_close()

    def polls(self) -> list[dict]:
        return [r for r in self.requests if r["path"].startswith("/v1/image-projects/")]

    def creates(self) -> list[dict]:
        return [r for r in self.requests if r["path"] == "/v1/ai-image-generator"]
