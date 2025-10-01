# examples/mock_backend.py
from http.server import BaseHTTPRequestHandler, HTTPServer
import json, gzip, io

class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length)
        if self.headers.get("Content-Encoding") == "gzip":
            body = gzip.GzipFile(fileobj=io.BytesIO(body)).read()
        data = json.loads(body.decode("utf-8"))
        aircraft = len(data.get("aircraft", []))
        print(f"[mock] received {aircraft} aircraft from site={data.get('site_id')}")
        self.send_response(200); self.end_headers()
        self.wfile.write(b'{"ok":true}')

if __name__ == "__main__":
    HTTPServer(("0.0.0.0", 8081), Handler).serve_forever()