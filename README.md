# Touchway ADS-B Forwarder

A lightweight Python service that reads ADS-B data from `dump1090-fa` and forwards it to a backend API.

The project supports two modes:

- Production: install the native Debian package `touchway-adsb-forwarder_<version>_all.deb` and run `touchway-adsb-forwarder.service`.
- Development: run the source locally with `docker-compose.dev.yml` and the sample feed.

## Features

- Reads aircraft data from `dump1090-fa` at `/run/dump1090-fa/aircraft.json`.
- Sends the existing compact JSON payload without changing the HTTP contract.
- Supports optional gzip compression.
- Supports optional HMAC-SHA256 request signing.
- Uses only the Python standard library at runtime.
- Preserves the existing environment variables and Piaware fallback for `FEEDER_ID`.

## Repository Structure

```text
touchway-adsb-forwarder/
├─ .docker/
│  └─ dev.env
├─ .github/
│  ├─ scripts/
│  │  └─ next_semver.py
│  └─ workflows/
│     └─ build.yml
├─ packaging/
│  ├─ touchway-adsb-forwarder.service
│  ├─ postinst
│  ├─ postrm
│  └─ prerm
├─ scripts/
│  └─ build_deb.py
├─ docker-compose.dev.yml
├─ examples/
│  └─ aircraft.sample.json
├─ forward.py
├─ tests/
└─ .env.example
```

## Production

### Supported target

- Debian 12
- Raspberry Pi OS Bookworm

### Public deployment interfaces

- Package: `touchway-adsb-forwarder_<version>_all.deb`
- Service: `touchway-adsb-forwarder.service`
- Config: `/etc/touchway-adsb-forwarder/forwarder.env`
- Installed code: `/usr/lib/touchway-adsb-forwarder/forward.py`

### Install

1. Download `touchway-adsb-forwarder_<version>_all.deb` and `touchway-adsb-forwarder_<version>_all.deb.sha256` from the GitHub Release.
2. Verify the checksum.
3. Install the package.
4. Edit `/etc/touchway-adsb-forwarder/forwarder.env`.
5. Enable and start the service.

```bash
sha256sum -c touchway-adsb-forwarder_<version>_all.deb.sha256
sudo apt install ./touchway-adsb-forwarder_<version>_all.deb
sudoedit /etc/touchway-adsb-forwarder/forwarder.env
sudo systemctl enable --now touchway-adsb-forwarder
```

The package installs the service stopped and disabled. It does not enable or start the unit automatically.
You must edit `/etc/touchway-adsb-forwarder/forwarder.env` before the first `enable --now`.

### Configuration

Set `FEEDER_ID` explicitly for native installs when possible. If you leave it blank, the forwarder still falls back to `/var/cache/piaware/feeder_id`.

The default source file for production remains:

```bash
SOURCE_FILE=/run/dump1090-fa/aircraft.json
```

### Verify

```bash
sudo systemctl status touchway-adsb-forwarder
sudo journalctl -u touchway-adsb-forwarder -f
```

### Upgrade

Install the new package version over the existing one:

```bash
sudo apt install ./touchway-adsb-forwarder_<new-version>_all.deb
```

The package reloads `systemd` and restarts `touchway-adsb-forwarder.service` automatically during upgrade.
If that restart fails, `apt` fails and you should inspect:

```bash
sudo systemctl status touchway-adsb-forwarder
sudo journalctl -u touchway-adsb-forwarder -n 100
```

### Rollback

Reinstall the previous package version:

```bash
sudo apt install ./touchway-adsb-forwarder_<previous-version>_all.deb
```

Rollback follows the same package lifecycle as upgrade: the unit is restarted automatically and package configuration fails if the restart fails.

### Manual Raspberry Pi validation

For a release candidate on Raspberry Pi OS Bookworm:

1. Install the `.deb` from the release.
2. Keep `SOURCE_FILE=/run/dump1090-fa/aircraft.json`.
3. Start `touchway-adsb-forwarder.service`.
4. Confirm normal forwarding in `journalctl`.
5. Reboot and confirm the service auto-starts.

## Development

Local development stays Docker-based and uses the sample feed.

```bash
docker compose -f docker-compose.dev.yml up --build
```

The development stack uses:

- source bind-mount of `forward.py`
- sample feed at `examples/aircraft.sample.json`
- defaults from `.docker/dev.env`

To inspect the rendered stack:

```bash
docker compose -f docker-compose.dev.yml config
```

## Packaging

Build a local package with the git-based fallback version:

```bash
python3 scripts/build_deb.py
```

Build a release package explicitly:

```bash
PACKAGE_VERSION=1.2.3 python3 scripts/build_deb.py --output-dir dist
```

The local fallback version format is:

```text
0.0.0~git<shortsha>
```

## GitHub Actions and Releases

Every PR and push validates:

- `pytest -q`
- `.deb` build with `scripts/build_deb.py`
- `dpkg-deb -I` and `dpkg-deb -c`
- package installation on the runner
- one-shot execution of the installed forwarder against a sample feed and a dead local port
- `systemd-analyze verify /lib/systemd/system/touchway-adsb-forwarder.service`

On `main`, the workflow keeps the existing semver rules:

- `feat` => minor bump
- `fix`, `perf`, `refactor`, `build`, `chore` => patch bump
- `!` or `BREAKING CHANGE:` => major bump
- `docs`, `test`, `style`, `ci` => no release by themselves

When a semver release is created or reused on `HEAD`, GitHub Actions uploads:

- `touchway-adsb-forwarder_<version>_all.deb`
- `touchway-adsb-forwarder_<version>_all.deb.sha256`

## Environment Variables

Runtime variables belong in `/etc/touchway-adsb-forwarder/forwarder.env` in production and `.docker/dev.env` for local development.

| Variable | Description | Default |
| --- | --- | --- |
| `BACKEND_URL` | Target API endpoint | none; required |
| `FEEDER_ID` | Unique feeder identifier; recommended explicitly for native install | auto-detect from Piaware if omitted |
| `HMAC_SECRET` | Secret used to sign payloads | none; required |
| `INTERVAL_SEC` | Interval between sends, in seconds | `3` |
| `HTTP_TIMEOUT_SEC` | HTTP timeout, in seconds | `5` |
| `USE_GZIP` | Compress payload with gzip when set to `1` | `1` |
| `SOURCE_FILE` | Path to `aircraft.json` on the host or in the dev container | `/run/dump1090-fa/aircraft.json` |

If `FEEDER_ID` is omitted, the forwarder falls back to `/var/cache/piaware/feeder_id`.

## Security

- Runs as the `touchway-adsb-forwarder` system user.
- Uses `NoNewPrivileges=yes`.
- Uses `PrivateTmp=yes`.
- Uses `ProtectSystem=strict`.
- Uses `ProtectHome=yes`.
- Uses read-only access to `/run/dump1090-fa` and `/var/cache/piaware`.
- Supports HMAC signing so the backend can verify authenticity.

### HMAC request signing

If `HMAC_SECRET` is set, the forwarder computes `HMAC_SHA256(secret, request_body)` and sends the hex digest in the `X-Feeder-Signature` header.

Backend expectations:

1. Read the raw request body exactly as received.
2. Compute the same HMAC with the feeder secret.
3. Compare the digest using a constant-time comparison.
4. Reject missing or invalid signatures.
