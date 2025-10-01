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

  ```bash
  docker compose --env-file docker/dev.env/forwarder.dev.env -f docker-compose.dev.yml config
  ```

  Use the `config` view above to confirm what Compose will pass to the container when debugging environment overrides.

### 2. Production (on feeder)

1. Copy the repo files to your feeder device (e.g., Raspberry Pi). A common layout is to clone into `/opt/adsb-forwarder`:

   ```bash
   sudo install -d -m 755 /opt/adsb-forwarder
   sudo chown "$USER":"$USER" /opt/adsb-forwarder
   git clone https://github.com/touchway/touchway-adsb-forwarder.git /opt/adsb-forwarder
   ```

   Adjust the Git URL if you deploy from a fork.

2. Provision an environment file on the device (recommended for both manual runs and systemd):

   ```bash
   sudo cp /opt/adsb-forwarder/examples/forwarder.env.example /opt/adsb-forwarder/forwarder.env
   sudo nano /opt/adsb-forwarder/forwarder.env  # fill in BACKEND_URL/FEEDER_ID/SITE_ID/etc.
   ```

   > **Why not `~/.bashrc`?** Shell exports only exist for your interactive session; services started at boot (e.g., via systemd) won’t inherit them. A dedicated env file at `/opt/adsb-forwarder/forwarder.env` works for both manual and automated starts while keeping secrets out of your shell history.

   The repository’s `.gitignore` already excludes `forwarder.env`/`*.env`, so you won’t accidentally commit secrets.

3. Deploy with Docker Compose (the production file already references `/opt/adsb-forwarder/forwarder.env` via `env_file`):

```bash
cd /opt/adsb-forwarder
docker compose -f docker-compose.prod.yml up -d
```

   To double-check how variables resolve before starting the stack, inspect the rendered configuration:

   ```bash
   docker compose -f docker-compose.prod.yml config
   ```

   Compose evaluates variables in this order. Later sources override earlier ones, so exporting a value in your shell (or passing a different `--env-file`) will win over the defaults baked into the compose files:

   | Priority | Source                                        | Notes |
   |----------|-----------------------------------------------|-------|
   | 1        | Shell exports / systemd unit `Environment=`   | Highest precedence; great for one-off overrides |
   | 2        | `docker compose --env-file path.env`          | Useful for swapping between env files without editing compose |
   | 3        | `.env` beside the compose file                | Automatically picked up if present |
   | 4        | `env_file:` entries inside the compose stack  | Where production defaults like `/opt/adsb-forwarder/forwarder.env` live |
   | 5        | Hardcoded `environment:` values in the compose| Final fallback defaults (e.g., `INTERVAL_SEC:-3`) |

   When you provide a different `--env-file`, Compose replaces the values coming from `env_file:` entries. Document which file should be used in production (e.g., `/opt/adsb-forwarder/forwarder.env`) so operators know what will be overridden.

4. (Optional) Manage the service with systemd so it starts on boot. This unit assumes the repo lives in `/opt/adsb-forwarder` and uses the same env file:

   ```ini
   # /etc/systemd/system/adsb-forwarder-compose.service
   [Unit]
   Description=ADSB forwarder via Docker Compose
   After=docker.service network-online.target
   Wants=docker.service network-online.target

   [Service]
   Type=oneshot
   RemainAfterExit=yes
   WorkingDirectory=/opt/adsb-forwarder
   ExecStart=/usr/bin/docker compose -f docker-compose.prod.yml up -d
   ExecStop=/usr/bin/docker compose -f docker-compose.prod.yml down

   [Install]
   WantedBy=multi-user.target
   ```

   Enable it with `sudo systemctl enable --now adsb-forwarder-compose.service`.

5. Check logs:

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
| `HMAC_SECRET`      | Secret key for signing payloads (required in prod) | **req** |
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
