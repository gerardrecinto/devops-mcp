FROM python:3.15.2-slim@sha256:65a65fc7b30b06cb6df4930fd4650697cb23f4c2698ab81fc87e4b031bc36928 AS builder

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src/ src/

RUN pip install --no-cache-dir --prefix=/install ".[azure,gcp,slack]"

FROM python:3.15.2-slim@sha256:65a65fc7b30b06cb6df4930fd4650697cb23f4c2698ab81fc87e4b031bc36928

RUN groupadd --gid 1000 devops-mcp \
    && useradd --uid 1000 --gid devops-mcp --create-home --shell /usr/sbin/nologin devops-mcp

COPY --from=builder /install /usr/local

WORKDIR /home/devops-mcp
USER devops-mcp

ENV PYTHONUNBUFFERED=1

CMD ["devops-mcp"]
