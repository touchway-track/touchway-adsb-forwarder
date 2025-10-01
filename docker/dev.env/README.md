# Development environment overrides

Place per-developer Compose overrides here, e.g. `forwarder.dev.env`.

Add `KEY=value` lines to the file and point Docker Compose at it:

```bash
docker compose --env-file docker/dev.env/forwarder.dev.env -f docker-compose.dev.yml up --build
```

This directory is git-ignored so secrets stay local.
