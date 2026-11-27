FROM python:3.15.1-slim@sha256:533b0b2f9b5d46fd097091cf826f27902f1d6c3bca714b6dc74551356aa97a51 AS builder

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src/ src/

RUN pip install --no-cache-dir --prefix=/install ".[azure,gcp,slack]"

FROM python:3.15.1-slim@sha256:533b0b2f9b5d46fd097091cf826f27902f1d6c3bca714b6dc74551356aa97a51

RUN groupadd --gid 1000 devops-mcp \
    && useradd --uid 1000 --gid devops-mcp --create-home --shell /usr/sbin/nologin devops-mcp

COPY --from=builder /install /usr/local

WORKDIR /home/devops-mcp
USER devops-mcp

ENV PYTHONUNBUFFERED=1

CMD ["devops-mcp"]
