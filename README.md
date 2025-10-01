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
- Environment variables have sensible defaults baked into `docker-compose.dev.yml`. If you need to override them, drop a file such as `docker/dev.env/forwarder.dev.env` (git-ignored) with `KEY=value` pairs and start the stack with:

  ```bash
  docker compose --env-file docker/dev.env/forwarder.dev.env -f docker-compose.dev.yml up --build
  ```

  Any values defined in the override file (or exported in your shell) will replace the defaults.

### 2. Production (on feeder)

1. Copy the repo files to your feeder device (e.g., Raspberry Pi).
2. Decide how you want to provide secrets/configuration:

   - **Shell exports (e.g., `.bashrc`)** – add the required variables and reload your shell:

     ```bash
     export BACKEND_URL="https://your-backend/api/adsb/ingest"
     export FEEDER_ID="ff-vcp-01"
     export SITE_ID="vcp-site"
     export HMAC_SECRET="supersecret"
     export INTERVAL_SEC=3
     export USE_GZIP=1
     export HTTP_TIMEOUT_SEC=5
     export SOURCE_FILE=/run/dump1090-fa/aircraft.json
     ```

     You can place those `export` lines in `~/.bashrc` or `~/.profile` so they persist across sessions.

   - **Dedicated env file** – copy `examples/forwarder.env.example`, fill in your values, and pass it to Compose when launching:

     ```bash
     cp examples/forwarder.env.example forwarder.prod.env
     # edit forwarder.prod.env with your secrets
     ```

3. Deploy with Docker Compose (choose the approach that matches how you supplied the variables):

```bash
cd /opt/adsb-forwarder
# Drop the --env-file flag if you exported variables instead of using a file.
docker compose \
  --env-file forwarder.prod.env \
  -f docker-compose.prod.yml up -d
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
