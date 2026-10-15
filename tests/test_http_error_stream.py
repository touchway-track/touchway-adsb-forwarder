import os
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("chunked", [False, True])
def test_error_stream_does_not_block_next_batch(tmp_path, chunked):
    """A timely but endless body must not monopolize the forwarding loop."""
    sample = tmp_path / "aircraft.json"
    sample.write_text('{"aircraft": []}', encoding="utf-8")
    stop = threading.Event()
    requests = []

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *args):
            pass

        def do_POST(self):
            self.rfile.read(int(self.headers["Content-Length"]))
            requests.append(self.path)
            if len(requests) > 1:
                self.send_response(202)
                self.send_header("Content-Length", "0")
                self.end_headers()
                return

            self.send_response(503)
            if chunked:
                self.send_header("Transfer-Encoding", "chunked")
            else:
                # Advertise a huge body without allocating it in the test.
                self.send_header("Content-Length", str(2 ** 30))
            self.end_headers()
            # Keep sending more frequently than the client's idle timeout.
            while not stop.is_set():
                try:
                    self.wfile.write(b"1\r\nx\r\n" if chunked else b"x")
                    self.wfile.flush()
                except OSError:
                    break
                stop.wait(0.02)

    with ThreadingHTTPServer(("127.0.0.1", 0), Handler) as server:
        thread = threading.Thread(
            target=server.serve_forever, kwargs={"poll_interval": 0.01}
        )
        thread.start()
        env = os.environ.copy()
        env.update(
            BACKEND_URL=f"http://127.0.0.1:{server.server_port}/ingest",
            FEEDER_ID="stream-test",
            SOURCE_FILE=str(sample),
            HTTP_TIMEOUT_SEC="0.25",
            NO_PROXY="127.0.0.1",
            no_proxy="127.0.0.1",
        )
        try:
            result = subprocess.run(
                [
                    sys.executable,
                    "-c",
                    "import forward; "
                    "assert forward.send_once() is False; "
                    "assert forward.send_once() is True",
                ],
                cwd=ROOT,
                env=env,
                capture_output=True,
                text=True,
                timeout=3,
            )
        finally:
            stop.set()
            server.shutdown()
            thread.join(timeout=3)

    assert result.returncode == 0, result.stderr
    assert "http error 503" in result.stderr
    assert "202 aircraft=0" in result.stdout
    assert requests == ["/ingest", "/ingest"]
