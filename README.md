# ADS-B Forwarder

A lightweight Python service that reads local ADS-B data from `dump1090-fa` and forwards it to a backend API.

The project supports two operating modes:

- Development: run local source code with `docker-compose.dev.yml`.
- Production: deploy a published Docker image from GHCR with `docker-compose.prod.yml`.

## Features

- Reads aircraft data from `dump1090-fa` at `/run/dump1090-fa/aircraft.json`.
- Sends compact JSON payloads to a backend endpoint.
- Supports optional gzip compression.
- Supports optional HMAC-SHA256 request signing.
- Uses only the Python standard library at runtime.
- Ships as a multi-arch Docker image for `linux/arm/v7`, `linux/arm64`, and `linux/amd64`.

## Repository Structure

```text
adsb-forwarder/
├─ .docker/
│  └─ dev.env
├─ .github/
│  └─ workflows/
│     └─ build.yml
├─ compose.env.example
├─ docker-compose.dev.yml
├─ docker-compose.prod.yml
├─ Dockerfile
├─ examples/
│  └─ aircraft.sample.json
├─ forward.py
├─ tests/
│  └─ test_forward.py
└─ .env.example
```

## Development

Run the forwarder locally against the sample aircraft feed:

```bash
docker compose -f docker-compose.dev.yml up --build
```

Development uses:

- source bind-mount of `forward.py`
- sample feed at `examples/aircraft.sample.json`
- defaults from `.docker/dev.env`

To inspect the rendered stack:

```bash
docker compose -f docker-compose.dev.yml config
```

## Production

Production deploys a published image, not a host-mounted `forward.py`.

### 1. Initial setup on the feeder

Clone the repo once so the host has the Compose file and templates:

```bash
sudo install -d -m 755 /opt/adsb-forwarder
sudo chown "$USER":"$USER" /opt/adsb-forwarder
git clone https://github.com/touchway-track/touchway-adsb-forwarder.git /opt/adsb-forwarder
```

Create the runtime env file used by the application:

```bash
cp /opt/adsb-forwarder/.env.example /opt/adsb-forwarder/forwarder.env
nano /opt/adsb-forwarder/forwarder.env
```

`/opt/adsb-forwarder/forwarder.env` is only for application runtime values such as `BACKEND_URL`, `HMAC_SECRET`, and optional `FEEDER_ID`.

Create the Compose variable file used to select the image tag:

```bash
cp /opt/adsb-forwarder/compose.env.example /opt/adsb-forwarder/.env
nano /opt/adsb-forwarder/.env
```

`/opt/adsb-forwarder/.env` is only for Compose interpolation and must define `IMAGE_TAG=...`.

### 2. Deploy

```bash
cd /opt/adsb-forwarder
docker compose -f docker-compose.prod.yml pull
docker compose -f docker-compose.prod.yml up -d
```

The production stack mounts only runtime files and directories from the host:

- `/opt/adsb-forwarder/forwarder.env`
- `/run/dump1090-fa`
- `/var/cache/piaware`

The container image already contains `forward.py`.

### 3. Upgrade

Edit `/opt/adsb-forwarder/.env` and change `IMAGE_TAG` to the new published tag, then run:

```bash
cd /opt/adsb-forwarder
docker compose -f docker-compose.prod.yml pull
docker compose -f docker-compose.prod.yml up -d
```

### 4. Rollback

Set `IMAGE_TAG` back to the previous tag in `/opt/adsb-forwarder/.env`, then run the same commands:

```bash
cd /opt/adsb-forwarder
docker compose -f docker-compose.prod.yml pull
docker compose -f docker-compose.prod.yml up -d
```

### 5. Inspect the rendered production stack

```bash
docker compose -f docker-compose.prod.yml config
```

### Optional: start on boot with systemd

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

Enable it with:

```bash
sudo systemctl enable --now adsb-forwarder-compose.service
```

The systemd unit is only for boot-time startup. Normal upgrades and rollbacks should still be done by changing `IMAGE_TAG` and running `pull` plus `up -d`.

## GitHub Actions and Image Tags

GitHub Actions validates every PR with:

- `pytest -q`
- `docker build -t adsb-forwarder:pr .`
- a short smoke test against the built image

Publication rules:

- Push to `main`: publish `ghcr.io/touchway-track/touchway-adsb-forwarder:sha-<commit>`
- Push tag `vX.Y.Z`: publish both `vX.Y.Z` and `sha-<commit>`
- No `latest` tag is published

Production should normally consume immutable tags such as `v1.2.3` or `sha-<commit>`.

## Environment Variables

Runtime variables belong in `/opt/adsb-forwarder/forwarder.env`.

| Variable           | Description                                                   | Default |
|--------------------|---------------------------------------------------------------|---------|
| `BACKEND_URL`      | Target API endpoint                                           | none; required |
| `FEEDER_ID`        | Unique feeder identifier; overrides Piaware auto-detect       | auto-detect from Piaware if omitted |
| `HMAC_SECRET`      | Secret used to sign payloads                                  | none; required in supported production deploy |
| `INTERVAL_SEC`     | Interval between sends, in seconds                            | `3` |
| `HTTP_TIMEOUT_SEC` | HTTP timeout, in seconds                                      | `5` |
| `USE_GZIP`         | Compress payload with gzip when set to `1`                    | `1` |
| `SOURCE_FILE`      | Path to `aircraft.json` inside the container                  | `/run/dump1090-fa/aircraft.json` |

If `FEEDER_ID` is omitted, the forwarder falls back to `/var/cache/piaware/feeder_id`.

`IMAGE_TAG` does not belong in `forwarder.env`; it belongs in `/opt/adsb-forwarder/.env`.

## Security

- Runs as non-root inside Docker.
- Drops all Linux capabilities.
- Uses a read-only root filesystem.
- Uses `tmpfs` for `/tmp`.
- Supports HMAC signing so the backend can verify authenticity.

### HMAC request signing

If `HMAC_SECRET` is set, the forwarder computes `HMAC_SHA256(secret, request_body)` and sends the hex digest in the `X-Feeder-Signature` header.

Backend expectations:

1. Read the raw request body exactly as received.
2. Compute the same HMAC with the feeder secret.
3. Compare the digest using a constant-time comparison.
4. Reject missing or invalid signatures.

## Logs

```bash
docker logs -f adsb-forwarder
```
