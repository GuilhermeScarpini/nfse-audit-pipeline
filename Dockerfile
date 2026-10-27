# syntax=docker/dockerfile:1

# ---------------------------------------------------------------------------
# Stage 1: builder. Has uv; resolves and installs dependencies into /app/.venv.
# ---------------------------------------------------------------------------
FROM ghcr.io/astral-sh/uv:0.13.6@sha256:af22a52f5eafef3d78e551599d405c02df61919d18028f0cea8eda93bc9986d0 AS uv

FROM python:3.12-slim-trixie@sha256:a6e34c598f2467ed0e9a8d349809fcd8b5c603269512df273a0bb1784edc11b1 AS builder
COPY --from=uv /uv /usr/local/bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/app/.venv

WORKDIR /app

# Optional extra CA for builds behind a TLS-inspecting proxy, passed as a build
# secret (docker build --secret id=extra_ca,src=extra-ca.crt). It is combined with the
# system bundle in a tmpfs, so it never ends up in an image layer.
COPY --chmod=755 <<'EOF' /usr/local/bin/with-extra-ca
#!/bin/sh
set -e
if [ -s /run/secrets/extra_ca ]; then
    cat /etc/ssl/certs/ca-certificates.crt /run/secrets/extra_ca > /tmp/ca.pem
    export SSL_CERT_FILE=/tmp/ca.pem
fi
exec "$@"
EOF

# Dependencies first: this layer is reused until uv.lock changes.
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=secret,id=extra_ca \
    --mount=type=tmpfs,target=/tmp \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    with-extra-ca uv sync --locked --no-dev --no-install-project

# Then the project itself, installed as a regular package (not editable),
# so the runtime image does not need the source tree.
COPY pyproject.toml uv.lock README.md ./
COPY src ./src
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=secret,id=extra_ca \
    --mount=type=tmpfs,target=/tmp \
    with-extra-ca uv sync --locked --no-dev --no-editable

# ---------------------------------------------------------------------------
# Stage 2: runtime. Only Python and the virtualenv; no uv, no compilers, no source.
# ---------------------------------------------------------------------------
FROM python:3.12-slim-trixie@sha256:a6e34c598f2467ed0e9a8d349809fcd8b5c603269512df273a0bb1784edc11b1 AS runtime

RUN groupadd --system --gid 10001 app \
    && useradd --system --uid 10001 --gid app --no-create-home --shell /usr/sbin/nologin app \
    && mkdir /data \
    && chown app:app /data

# Owned by root: the app user can run the code but not change it.
COPY --from=builder /app/.venv /app/.venv

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    DATA_DIR=/data

USER app
WORKDIR /app
EXPOSE 8000

# The API by default; the worker overrides the command (see docker-compose.yml).
CMD ["uvicorn", "nfse_audit.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
