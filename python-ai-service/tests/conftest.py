"""Shared test helpers."""

import http.server
import json
import threading

import pytest


class FakeProviderServer:
    """A tiny local web server that plays the part of an AI provider's API.

    Tests point the real SDK at it, so the real HTTP code runs, offline and free.
    Each request is recorded, and the replies are given in order (the last one
    repeats), so a test can script "fail once, then work".
    """

    def __init__(self, replies: list[tuple[int, dict]]):
        self.replies = replies
        self.requests: list[dict] = []
        outer = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_POST(self):
                length = int(self.headers.get("content-length", 0))
                outer.requests.append(
                    {
                        "path": self.path,
                        "headers": {k.lower(): v for k, v in self.headers.items()},
                        "body": json.loads(self.rfile.read(length) or b"null"),
                    }
                )
                status, payload = outer.replies[min(len(outer.requests), len(outer.replies)) - 1]
                raw = json.dumps(payload).encode()
                self.send_response(status)
                self.send_header("content-type", "application/json")
                self.send_header("content-length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

            def log_message(self, *args):  # keep the test output quiet
                pass

        self._server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        # A short poll interval makes stop() quick; the default waits half a second.
        self._thread = threading.Thread(
            target=lambda: self._server.serve_forever(poll_interval=0.01), daemon=True
        )

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self._server.server_address[1]}"

    def start(self) -> "FakeProviderServer":
        self._thread.start()
        return self

    def stop(self) -> None:
        self._server.shutdown()
        self._server.server_close()


@pytest.fixture
def fake_server():
    """Make a FakeProviderServer from a list of (status, json) replies."""
    started = []

    def make(replies: list[tuple[int, dict]]) -> FakeProviderServer:
        server = FakeProviderServer(replies).start()
        started.append(server)
        return server

    yield make

    for server in started:
        server.stop()
