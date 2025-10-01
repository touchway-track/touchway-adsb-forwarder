# ADS-B Forwarder

A lightweight Python service for collecting local ADS-B data from a FlightAware feeder (piaware / dump1090) and forwarding it securely to a central backend API. For more details on the feeder software, check the [official Piaware documentation](https://github.com/flightaware/piaware).

This project is designed to run both locally (for development/testing) and on production feeders (e.g., Raspberry Pi with FlightFeeder or Piaware).

---

## Features

- Reads aircraft JSON data from `dump1090-fa` (`/run/dump1090-fa/aircraft.json`).
- Forwards data as JSON (optionally compressed with Gzip).
- Optional HMAC-SHA256 signing for authenticity.
- Configurable interval and timeout.
- Minimal dependencies (stdlib only).
- Runs as a Docker container (slim Python image).

---

## Repository Structure

```
adsb-forwarder/
├─ forward.py                  # Main forwarder script
├─ examples/
│  ├─ aircraft.sample.json     # Sample aircraft JSON for testing
├─ .docker/
│  └─ dev.env                  # Default env vars consumed by docker-compose.dev.yml
├─ .env.example                # Template you can copy for other deployments
├─ docker-compose.dev.yml      # Local dev stack (forwarder only)
├─ docker-compose.prod.yml     # Production stack (forwarder only)
├─ Dockerfile                  # Docker build definition
├─ .dockerignore
└─ README.md
```

---

## Quick Start

### 1. Development (local, without feeder)

Run the forwarder against your locally running backend using the sample JSON from this repository.

```bash
# optional: copy .docker/dev.env and tweak if your backend isn't on localhost
docker compose -f docker-compose.dev.yml up --build
```

- The forwarder reads `examples/aircraft.sample.json` and sends it every few seconds.
- `docker-compose.dev.yml` loads `.docker/dev.env`; copy or edit that file to point at your local backend (e.g., `BACKEND_URL=http://localhost:8080/adsb/ingest`).
- Prefer `docker run` over Compose? Mount `.docker/dev.env` (or a copy) to reuse the same localhost defaults for quick experiments.
- To preview the final configuration with your overrides applied, run:

  ```bash
  docker compose -f docker-compose.dev.yml config
  ```

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
   sudo cp /opt/adsb-forwarder/.env.example /opt/adsb-forwarder/forwarder.env
   sudo nano /opt/adsb-forwarder/forwarder.env  # fill in BACKEND_URL/FEEDER_ID/etc.
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
| `BACKEND_URL`      | Target API endpoint                                | `http://localhost:8080/adsb/ingest` (dev) |
| `FEEDER_ID`        | Unique feeder identifier (overrides Piaware auto-detect) | optional |
| `HMAC_SECRET`      | Secret key for signing payloads (required in prod) | **req** |
| `INTERVAL_SEC`     | Interval between sends (seconds)                   | `3`     |
| `HTTP_TIMEOUT_SEC` | HTTP request timeout (seconds)                     | `5`     |
| `USE_GZIP`         | Compress payload with Gzip (1 = enabled)           | `1`     |
| `SOURCE_FILE`      | Path to `aircraft.json`                            | `/run/dump1090-fa/aircraft.json` |

> If `FEEDER_ID` is omitted, the forwarder automatically reads `/var/cache/piaware/feeder_id` generated by Piaware during feeder registration.

---

## Security

- Runs as a non-root user inside Docker.
- Drops all Linux capabilities.
- Uses read-only root filesystem + tmpfs for `/tmp`.
- Optional request signing with HMAC.
- Can be deployed on a private tailnet (e.g., via Tailscale).

### HMAC request signing

The forwarder can sign each payload with an **HMAC-SHA256** digest so the backend can prove the data really came from your feeder
and was not tampered with in transit. This strategy uses a shared secret (`HMAC_SECRET`) that exists only on the feeder and the
receiving API.

#### When to use it

- **Production** deployments should always enable HMAC by setting the `HMAC_SECRET` environment variable. The secret can be any
  sufficiently random string (for example, 32+ bytes generated with `openssl rand -hex 32`).
- **Development** environments may omit the variable to simplify local testing. When `HMAC_SECRET` is unset the forwarder skips
  signing entirely.

#### How it works

1. The forwarder serializes the request body as JSON.
2. It computes `HMAC_SHA256(secret=HMAC_SECRET, message=payload_bytes)`.
3. The resulting digest is hex-encoded and attached to the HTTP request as the `X-ADSB-Signature` header.

Because HMAC uses the shared secret on both ends, any change to the payload or missing/incorrect secret causes the server to
calculate a different digest and reject the request.

#### Backend expectations

Your API should perform the same computation before accepting a payload:

1. Read the raw request body exactly as received.
2. Recreate the HMAC using the shared secret (`HMAC_SECRET`).
3. Compare the digest to the value from the `X-ADSB-Signature` header using a **constant-time** comparison routine to avoid
   timing attacks.
4. Reject the request (e.g., HTTP 401/403) if the header is missing or the signature does not match.

If you are building a new endpoint, require both the `X-ADSB-Signature` header and the `FEEDER_ID` metadata so the backend can
associate the signing secret with the correct feeder record.

---

## Development Notes

- The project is intentionally minimal (no external Python libs) for compatibility with constrained devices.
- For production, you may want to version-pin the Python slim image and monitor CVEs.

---

## License

MIT — use freely in your own projects.
