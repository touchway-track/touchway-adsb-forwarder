# Development environment overrides

Place per-developer Compose overrides here, e.g. `forwarder.dev.env`.

Add `KEY=value` lines to the file and point Docker Compose at it:

```bash
docker compose --env-file docker/dev.env/forwarder.dev.env -f docker-compose.dev.yml up --build
```

To preview what Compose will inject, render the combined config:

```bash
docker compose --env-file docker/dev.env/forwarder.dev.env -f docker-compose.dev.yml config
```

Example file contents:

```
BACKEND_URL=http://mock-backend:8081/adsb/ingest
FEEDER_ID=ff-dev-yourname
SITE_ID=local-lab
```

This directory is git-ignored so secrets stay local.
