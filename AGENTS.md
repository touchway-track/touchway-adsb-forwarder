# AGENTS.md

This file provides **agent-focused guidance** for working with the ADS-B Forwarder project.  
It complements the human-friendly `README.md` by documenting extra details coding agents need: build steps, conventions, and CI/CD expectations.

---

## Project Overview

- A Python-based forwarder that reads ADS-B data from `dump1090-fa` and POSTs it to a backend API.
- Runs inside a minimal Docker container (`python:3.12-slim-bookworm`).
- Designed for deployment on Raspberry Pi devices running FlightAware Feeder (piaware).

---

## Development Environment

### Local Development

- Use `docker compose -f docker-compose.dev.yml up --build` to run the forwarder against your local backend (Compose loads `.env` automatically).
- Forwarder reads from `examples/aircraft.sample.json` instead of a real feeder.
- Provide backend connection details via env vars or the repository-level `.env` (copy from `.env.example`).

### Python Environment

- Minimal dependencies: **stdlib only** (no external pip installs).
- If adding dependencies:
  - List them in `requirements.txt`.
  - Run inside a venv: `python -m venv venv && source venv/bin/activate`.
  - Pin versions explicitly.

### Docker

- Default base image: `python:3.12.6-slim-bookworm` (pinned).
- Always run as non-root (`USER 10001:10001`).
- Security hardening: `read_only: true`, `cap_drop: ALL`, `no-new-privileges:true`.

---

## Build & Release

### Local Build

```bash
docker build -t adsb-forwarder:dev .
```

### Multi-Arch Build (CI/CD)

- GitHub Actions workflow (`.github/workflows/build.yml`) builds for `arm/v7`, `arm64`, and `amd64` using `docker buildx`.
- Images are pushed to GitHub Container Registry (GHCR).

Example:

```bash
docker buildx build --platform linux/arm/v7,linux/arm64,linux/amd64   -t ghcr.io/<org>/adsb-forwarder:latest   --push .
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

- Use `docker-compose.dev.yml` to simulate data flow.
- Verify that the forwarder sends payloads to your locally running backend.

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

- Feeder devices run in remote/untrusted environments → containers must run locked down.
- Sensitive values (`HMAC_SECRET`, `BACKEND_URL`) are injected via `.env` file and **never** hardcoded.
- Always pin Docker base image version (avoid `latest`).
- CI/CD scans images with **Trivy** or **Docker Scout**; fail build on High/Critical CVEs.

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
2. Pull repo into `/opt/adsb-forwarder`.
3. Copy `forwarder.env` (per-device config).
4. Start container:

```bash
docker compose -f docker-compose.prod.yml up -d
```

5. Logs:

```bash
docker logs -f adsb-forwarder
```

---

## Notes for Agents

- If modifying CI workflows: keep build matrix for `arm/v7` (Raspberry Pi 3), `arm64` (Pi 4), and `amd64` ( local/dev).
- If updating Docker base image: bump patchversion only (e.g., `3.12.6 → 3.12.7`).
- Keep `forward.py` dependency-free unless absolutely necessary.
- When changing `forwarder.env` keys: update `README.md` and `.env.example`.

---
