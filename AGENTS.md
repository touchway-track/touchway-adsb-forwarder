# AGENTS.md

This file provides **agent-focused guidance** for working with the ADS-B Forwarder project.  
It complements the human-friendly `README.md` by documenting extra details coding agents need: build steps, conventions, and CI/CD expectations.

---

## Project Overview

- A Python-based forwarder that reads ADS-B data from `dump1090-fa` and POSTs it to a backend API.
- Production is a native Debian package for Debian 12 / Raspberry Pi OS Bookworm.
- Designed for deployment on Raspberry Pi devices running FlightAware Feeder (piaware).

---

## Development Environment

### Local Development

- Use `docker compose -f docker-compose.dev.yml up --build` to run the forwarder against your local backend (Compose loads `.env` automatically).
- Forwarder reads from `examples/aircraft.sample.json` instead of a real feeder.
- Use `.docker/dev.env` for local Docker defaults or override env vars directly when needed.

### Python Environment

- Minimal dependencies: **stdlib only** (no external pip installs).
- If adding dependencies:
  - List them in `requirements.txt`.
  - Run inside a venv: `python -m venv venv && source venv/bin/activate`.
  - Pin versions explicitly.

### Docker

- Docker is for local development only.
- `docker-compose.dev.yml` runs against the sample feed and should stay aligned with `forward.py`.
- Do not introduce Docker production steps, Compose production files, or GHCR release dependencies again.

---

## Build & Release

### Local Build

```bash
python3 scripts/build_deb.py
```

### Release Build (CI/CD)

- GitHub Actions workflow (`.github/workflows/build.yml`) builds `adsb-forwarder_<version>_all.deb`.
- Release assets are uploaded to the GitHub Release together with a `.sha256` checksum file.
- Package version in CI must use the semver version without the `v` prefix.

Example:

```bash
PACKAGE_VERSION=1.2.3 python3 scripts/build_deb.py --output-dir dist
```

---

## Testing

### Unit Testing

- Add tests in `tests/` folder (pytest recommended).
- Run locally:

```bash
pytest -v
```

### Integration Testing

- Use `docker-compose.dev.yml` to simulate data flow during local development.
- CI must also smoke test the installed `.deb` by running `/usr/lib/adsb-forwarder/forward.py --once`.
- CI must validate package upgrade and `--reinstall` flows, including the automatic restart contract for `adsb-forwarder.service`.

---

## Code Style

- Use **PEP8** guidelines.
- Run formatting before commits:

```bash
python -m black .
python -m isort .
```

- Run lint:

```bash
flake8 forward.py
```

---

## Security Considerations

- Feeder devices run in remote/untrusted environments → the `systemd` service must stay locked down.
- Sensitive values (`HMAC_SECRET`, `BACKEND_URL`) are injected via `.env` file and **never** hardcoded.
- Keep the service running as the `adsb-forwarder` system user.
- Preserve `systemd` hardening such as `NoNewPrivileges=yes` and `ProtectSystem=strict`.

---

## PR / Commit Guidelines

- **Branch naming:** `feature/<name>`, `fix/<name>`, `chore/<name>`.
- **Commit messages:** Conventional Commits format. Examples:
  - `feat: add gzip compression to forwarder`
  - `fix: handle empty aircraft.json`
  - `chore: bump python base image`
- **PR titles:** `[forwarder] <short description>`.
- Always run `pytest` + `flake8` before merging.

---

## Deployment Steps

1. SSH into feeder via Tailscale.
2. Download `adsb-forwarder_<version>_all.deb` and `adsb-forwarder_<version>_all.deb.sha256`.
3. Verify the checksum.
4. Install the package with `apt`.
5. Edit `/etc/adsb-forwarder/forwarder.env`.
6. Enable and start the service:

```bash
sha256sum -c adsb-forwarder_<version>_all.deb.sha256
sudo apt install ./adsb-forwarder_<version>_all.deb
sudoedit /etc/adsb-forwarder/forwarder.env
sudo systemctl enable --now adsb-forwarder
```

The first install keeps the service stopped and disabled. Package upgrade, reinstall, and rollback restart the service automatically and fail the `apt` transaction if the restart fails.

7. Logs:

```bash
sudo systemctl status adsb-forwarder
sudo journalctl -u adsb-forwarder -f
```

---

## Notes for Agents

- If modifying CI workflows: preserve the `.deb` build, `dpkg-deb` inspection, install smoke test, upgrade/reinstall restart smoke, and `systemd-analyze verify`.
- Keep `forward.py` dependency-free unless absolutely necessary.
- When changing `forwarder.env` keys: update `README.md`, `.env.example`, and the package builder if paths change.

---
