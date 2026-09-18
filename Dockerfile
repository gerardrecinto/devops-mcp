FROM python:3.14.7-slim@sha256:cad9a2c871761c413caa6fdd6441c783451e740a48aaeba60ae62a8b53525ef6 AS builder

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src/ src/

RUN pip install --no-cache-dir --prefix=/install .

FROM python:3.14.7-slim@sha256:cad9a2c871761c413caa6fdd6441c783451e740a48aaeba60ae62a8b53525ef6

RUN groupadd --gid 1000 devops-mcp \
    && useradd --uid 1000 --gid devops-mcp --create-home --shell /usr/sbin/nologin devops-mcp

COPY --from=builder /install /usr/local

WORKDIR /home/devops-mcp
USER devops-mcp

ENV PYTHONUNBUFFERED=1

CMD ["devops-mcp"]
