# Stage 1: get uv binary from official image
FROM ghcr.io/astral-sh/uv:latest AS uv-bin

# Stage 2: app
FROM python:3.11-alpine

# Build deps for C extensions (ldap3 TLS, cryptography, argon2)
RUN apk add --no-cache gcc musl-dev libffi-dev openssl-dev

# Copy uv binary
COPY --from=uv-bin /uv /usr/local/bin/uv

WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --no-dev --frozen

COPY . .
RUN mkdir -p flask_session data

EXPOSE 8080
CMD ["uv", "run", "gunicorn", "run:app", \
     "--bind", "0.0.0.0:8080", \
     "--workers", "1", \
     "--threads", "4", \
     "--timeout", "60"]
