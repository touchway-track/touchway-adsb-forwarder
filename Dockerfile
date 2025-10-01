# Dockerfile
FROM python:3.12-slim

# segurança & mínima superfície
RUN useradd -u 10001 -r -s /usr/sbin/nologin appuser \
  && apt-get update && apt-get install -y --no-install-recommends ca-certificates \
  && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY forward.py /app/forward.py
RUN chmod 0555 /app/forward.py

USER 10001:10001
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

# rootfs read-only: crie /tmp e /app/state em tempo de execução via tmpfs
CMD ["python", "/app/forward.py"]