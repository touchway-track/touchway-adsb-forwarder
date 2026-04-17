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
   sudo nano /opt/adsb-forwarder/forwarder.env  # fill in BACKEND_URL/HMAC_SECRET and optionally FEEDER_ID
   ```

   > **Why not `~/.bashrc`?** Shell exports only exist for your interactive session; services started at boot (e.g., via systemd) won’t inherit them. A dedicated env file at `/opt/adsb-forwarder/forwarder.env` works for both manual and automated starts while keeping secrets out of your shell history.

   The repository’s `.gitignore` already excludes `forwarder.env`/`*.env`, so you won’t accidentally commit secrets.
   `.env.example` is production-oriented; `.docker/dev.env` remains the template used by `docker-compose.dev.yml`.

3. Deploy with Docker Compose (the production file already references `/opt/adsb-forwarder/forwarder.env` via `env_file`):

```bash
cd /opt/adsb-forwarder
docker compose -f docker-compose.prod.yml up -d
```

   This supported production flow does not require shell exports or `--env-file`. The container reads `/opt/adsb-forwarder/forwarder.env` directly at startup.

   The startup contract is:

   1. `BACKEND_URL` must be set in `/opt/adsb-forwarder/forwarder.env`.
   2. `HMAC_SECRET` must be set in `/opt/adsb-forwarder/forwarder.env`.
   3. `FEEDER_ID` is resolved from `forwarder.env` first; if omitted, the container falls back to `/var/cache/piaware/feeder_id`.
   4. `INTERVAL_SEC`, `USE_GZIP`, `HTTP_TIMEOUT_SEC`, and `SOURCE_FILE` fall back to the defaults built into `forward.py` if they are omitted.

   To inspect the rendered stack before startup, run:

   ```bash
   docker compose -f docker-compose.prod.yml config
   ```

   `config` confirms the stack shape, but the runtime presence of `BACKEND_URL` and `HMAC_SECRET` is enforced inside the container so the same `forwarder.env` contract works for manual runs and systemd.

   The production compose file bind-mounts `/run/dump1090-fa` and `/var/cache/piaware` from the host so the container can stream aircraft data and auto-detect the Piaware feeder ID. If you customize the stack, keep those mounts in place or provide equivalent `SOURCE_FILE` / `FEEDER_ID` values.

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
| `BACKEND_URL`      | Target API endpoint                                | none; required |
| `FEEDER_ID`        | Unique feeder identifier (overrides Piaware auto-detect) | auto-detect from Piaware if omitted |
| `HMAC_SECRET`      | Secret key for signing payloads                    | none; required in supported prod deploy |
| `INTERVAL_SEC`     | Interval between sends (seconds)                   | `3`     |
| `HTTP_TIMEOUT_SEC` | HTTP request timeout (seconds)                     | `5`     |
| `USE_GZIP`         | Compress payload with Gzip (1 = enabled)           | `1`     |
| `SOURCE_FILE`      | Path to `aircraft.json`                            | `/run/dump1090-fa/aircraft.json` |

> If `FEEDER_ID` is omitted, the production container reads `/var/cache/piaware/feeder_id` from the mounted Piaware cache directory.

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
3. The resulting digest is hex-encoded and attached to the HTTP request as the `X-Feeder-Signature` header.

Because HMAC uses the shared secret on both ends, any change to the payload or missing/incorrect secret causes the server to
calculate a different digest and reject the request.

#### Backend expectations

Your API should perform the same computation before accepting a payload:

1. Read the raw request body exactly as received.
2. Recreate the HMAC using the shared secret (`HMAC_SECRET`).
3. Compare the digest to the value from the `X-Feeder-Signature` header using a **constant-time** comparison routine to avoid
   timing attacks.
4. Reject the request (e.g., HTTP 401/403) if the header is missing or the signature does not match.

If you are building a new endpoint, require both the `X-Feeder-Signature` header and the `FEEDER_ID` metadata so the backend can
associate the signing secret with the correct feeder record.

---

## Development Notes

- The project is intentionally minimal (no external Python libs) for compatibility with constrained devices.
- For production, you may want to version-pin the Python slim image and monitor CVEs.

---

## License

MIT — use freely in your own projects.
