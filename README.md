# ADS-B Forwarder

A lightweight Python service for collecting local ADS-B data from a FlightAware feeder (piaware / dump1090) and forwarding it securely to a central backend API.

This project is designed to run both locally (for development/testing) and on production feeders (e.g., Raspberry Pi with FlightFeeder or Piaware).

---

## Features

- Reads aircraft JSON data from `dump1090-fa` (`/run/dump1090-fa/aircraft.json`).
- Forwards data as JSON (optionally compressed with Gzip).
- Optional HMAC-SHA256 signing for authenticity.
- Configurable interval and timeout.
- Minimal dependencies (stdlib only).
- Runs as a Docker container (slim Python image).
- Includes a mock backend for local testing.

---

## Repository Structure

```
adsb-forwarder/
├─ forward.py                  # Main forwarder script
├─ examples/
│  ├─ forwarder.env.example    # Example environment config
│  ├─ aircraft.sample.json     # Sample aircraft JSON for testing
│  └─ mock_backend.py          # Local mock server to receive POSTs
├─ docker-compose.dev.yml      # Local dev stack (mock backend + forwarder)
├─ docker-compose.prod.yml     # Production stack (forwarder only)
├─ Dockerfile                  # Docker build definition
├─ .dockerignore
└─ README.md
```

---

## Quick Start

### 1. Development (local, without feeder)

Run the forwarder against a mock backend using the sample JSON.

```bash
docker compose -f docker-compose.dev.yml up --build
```

- The mock backend runs on port `8081`.
- The forwarder reads `examples/aircraft.sample.json` and sends it every few seconds.
- Logs will show both sides (forwarder sends, mock receives).

### 2. Production (on feeder)

1. Copy the repo files to your feeder device (e.g., Raspberry Pi).
2. Prepare an environment file (`forwarder.env`):

```ini
BACKEND_URL=https://your-backend/api/adsb/ingest
FEEDER_ID=ff-vcp-01
SITE_ID=vcp-site
HMAC_SECRET=supersecret
INTERVAL_SEC=3
USE_GZIP=1
HTTP_TIMEOUT_SEC=5
SOURCE_FILE=/run/dump1090-fa/aircraft.json
```

3. Deploy with Docker Compose:

```bash
cd /opt/adsb-forwarder
docker compose -f docker-compose.prod.yml up -d
```

4. Check logs:

```bash
docker logs -f adsb-forwarder
```

---

## Environment Variables

| Variable           | Description                                        | Default |
|--------------------|----------------------------------------------------|---------|
| `BACKEND_URL`      | Target API endpoint                                | **req** |
| `FEEDER_ID`        | Unique feeder identifier                           | **req** |
| `SITE_ID`          | Site identifier                                    | **req** |
| `HMAC_SECRET`      | Secret key for signing payloads (optional)         | `""`    |
| `INTERVAL_SEC`     | Interval between sends (seconds)                   | `3`     |
| `HTTP_TIMEOUT_SEC` | HTTP request timeout (seconds)                     | `5`     |
| `USE_GZIP`         | Compress payload with Gzip (1 = enabled)           | `1`     |
| `SOURCE_FILE`      | Path to `aircraft.json`                            | `/run/dump1090-fa/aircraft.json` |

---

## Security

- Runs as a non-root user inside Docker.
- Drops all Linux capabilities.
- Uses read-only root filesystem + tmpfs for `/tmp`.
- Optional request signing with HMAC.
- Can be deployed on a private tailnet (e.g., via Tailscale).

---

## Development Notes

- `mock_backend.py` is useful for validating payloads before hitting your real API.
- The project is intentionally minimal (no external Python libs) for compatibility with constrained devices.
- For production, you may want to version-pin the Python slim image and monitor CVEs.

---

## License

MIT — use freely in your own projects.
