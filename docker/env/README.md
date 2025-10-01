# Environment file variants

The development compose stack automatically loads `dev.env` from the
repository root. That file ships with safe localhost defaults so you can
run:

```bash
docker compose -f docker-compose.dev.yml up --build
```

If you need alternative sets of values (QA, staging, etc.), drop them in
this directory. Because it remains git-ignored, you can store secrets or
work-in-progress overrides safely:

```bash
docker compose --env-file docker/env/forwarder.lab.env -f docker-compose.dev.yml up --build
```

Compose still honors the regular precedence chain, so exporting a value
in your shell (or providing another `--env-file`) will override
`dev.env`.
