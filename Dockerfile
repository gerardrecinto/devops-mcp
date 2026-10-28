FROM python:3.15.0-slim@sha256:f5b92f2a669a4c347044f29367f31983280b648250ca94dea66f98c53bc87e58 AS builder

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src/ src/

RUN pip install --no-cache-dir --prefix=/install ".[azure,gcp,slack]"

FROM python:3.15.0-slim@sha256:f5b92f2a669a4c347044f29367f31983280b648250ca94dea66f98c53bc87e58

RUN groupadd --gid 1000 devops-mcp \
    && useradd --uid 1000 --gid devops-mcp --create-home --shell /usr/sbin/nologin devops-mcp

COPY --from=builder /install /usr/local

WORKDIR /home/devops-mcp
USER devops-mcp

ENV PYTHONUNBUFFERED=1

CMD ["devops-mcp"]
