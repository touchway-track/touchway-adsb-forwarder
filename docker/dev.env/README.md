# Development environment overrides

Compose automatically loads `.env` files that sit next to the compose
configuration. For most local development, copy `.env.example` to `.env`
and edit it instead of dropping files in this directory.

If you prefer to keep multiple variants (e.g., `.env.qa`, `.env.lab`),
store them here and point Compose at the desired one explicitly:

```bash
docker compose --env-file docker/dev.env/forwarder.lab.env -f docker-compose.dev.yml up --build
```

Because this folder stays git-ignored, any secrets or experimental
overrides you add will remain local.
