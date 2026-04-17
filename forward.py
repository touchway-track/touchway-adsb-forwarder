#!/usr/bin/env python3
import gzip
import hashlib
import hmac
import json
import os
import sys
import time
from urllib import error, request

# === Configuration from environment variables ===
SRC = os.environ.get("SOURCE_FILE", "/run/dump1090-fa/aircraft.json")  # path to aircraft.json produced by dump1090-fa
URL = os.environ.get("BACKEND_URL")                                   # backend endpoint to send data
FEEDER_FILE = "/var/cache/piaware/feeder_id"                          # piaware-generated identifier file
SIGNATURE_HEADER = "X-Feeder-Signature"


def resolve_feeder_id():
    """Return the feeder identifier from env or Piaware cache."""

    feeder = os.environ.get("FEEDER_ID")
    if feeder:
        return feeder

    try:
        with open(FEEDER_FILE, "r", encoding="utf-8") as fh:
            feeder_file_value = fh.read().strip()
            if feeder_file_value:
                return feeder_file_value
    except OSError as exc:
        print(
            f"[forward] failed to read feeder id from '{FEEDER_FILE}': {exc}",
            file=sys.stderr,
        )

    return ""


FEEDER = resolve_feeder_id()                                           # feeder identifier
INTERVAL = float(os.environ.get("INTERVAL_SEC", "3"))                 # interval between requests (seconds)
SECRET = os.environ.get("HMAC_SECRET")                                # optional HMAC secret
USE_GZIP = os.environ.get("USE_GZIP", "1") == "1"                     # enable gzip compression
TIMEOUT = float(os.environ.get("HTTP_TIMEOUT_SEC", "5"))              # HTTP request timeout

# --- Utility: sign payload with HMAC (optional) ---
def sign(raw: bytes):
    return hmac.new(SECRET.encode(), raw, hashlib.sha256).hexdigest() if SECRET else ""

# --- Send one batch of aircraft data ---
def send_once():
    # Load JSON data from the dump1090 aircraft file
    try:
        with open(SRC, "r", encoding="utf-8") as f:
            d = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, OSError) as exc:
        print(f"[forward] failed to read source file '{SRC}': {exc}", file=sys.stderr)
        return False

    # Minimal payload with metadata and aircraft list
    payload = {
        "feeder_id": FEEDER,
        "now": d.get("now"),
        "messages": d.get("messages"),
        "aircraft": d.get("aircraft", []),
    }

    # Encode payload as JSON (compact separators to reduce size)
    raw = json.dumps(payload, separators=(",", ":")).encode()

    # Optionally compress with gzip
    body = gzip.compress(raw) if USE_GZIP else raw

    # Prepare HTTP headers
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "adsb-forwarder/1.0"
    }
    if USE_GZIP:
        headers["Content-Encoding"] = "gzip"

    # Optional: add HMAC signature header
    sig = sign(raw)
    if sig:
        headers[SIGNATURE_HEADER] = sig

    # Build POST request
    req = request.Request(URL, data=body, headers=headers, method="POST")

    try:
        # Send request
        with request.urlopen(req, timeout=TIMEOUT) as r:
            print(f"[forward] {r.status} aircraft={len(payload['aircraft'])}")
            return True
    except error.HTTPError as http_err:
        body_preview = ""
        try:
            body_bytes = http_err.read() if http_err.fp else b""
        except Exception as body_exc:  # pragma: no cover - defensive logging only
            body_preview = f"<failed to read error body: {body_exc}>"
        else:
            if body_bytes:
                decoded = body_bytes.decode("utf-8", errors="replace")
                truncated = decoded[:500]
                if len(decoded) > 500:
                    truncated += "... (truncated)"
                body_preview = truncated

        message = (
            f"[forward] http error {http_err.code} {http_err.reason} while POSTing {http_err.url or URL} "
            f"(feeder={FEEDER or '<unset>'}, aircraft={len(payload['aircraft'])}, timeout={TIMEOUT}s, gzip={'on' if USE_GZIP else 'off'})"
        )
        print(message, file=sys.stderr)

        suggestion = (
            "[forward] hint: verify BACKEND_URL matches a valid endpoint and that the backend allows POST requests for this path."
        )
        print(suggestion, file=sys.stderr)

        if body_preview:
            print(f"[forward] response body: {body_preview}", file=sys.stderr)

        return False
    except error.URLError as url_err:
        print(
            f"[forward] network error while reaching {URL}: {url_err.reason}",
            file=sys.stderr,
        )
        return False
    except Exception as exc:  # pragma: no cover - fallback guard
        # Log unexpected errors to stderr
        print(f"[forward] unexpected error: {exc}", file=sys.stderr)
        return False

# --- Main loop ---
def main():
    # Check required environment variables
    if not (URL and FEEDER):
        print(
            "BACKEND_URL and FEEDER_ID (env or /var/cache/piaware/feeder_id) are required",
            file=sys.stderr,
        )
        sys.exit(2)

    # One-shot mode (for testing)
    if "--once" in sys.argv:
        send_once()
        return

    # Continuous mode with exponential backoff on failure
    backoff = 1.0
    while True:
        ok = send_once()
        if ok:
            backoff = 1.0
        time.sleep(INTERVAL if ok else min(30.0, backoff := backoff * 2))

# Entry point
if __name__ == "__main__":
    main()
