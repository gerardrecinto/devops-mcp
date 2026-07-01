FROM python:3.12.13-slim@sha256:423ed6ab25b1921a477529254bfeeabf5855151dc2c3141699a1bfc852199fbf AS builder

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src/ src/

RUN pip install --no-cache-dir --prefix=/install .

FROM python:3.12.13-slim@sha256:423ed6ab25b1921a477529254bfeeabf5855151dc2c3141699a1bfc852199fbf

RUN groupadd --gid 1000 devops-mcp \
    && useradd --uid 1000 --gid devops-mcp --create-home --shell /usr/sbin/nologin devops-mcp

COPY --from=builder /install /usr/local

WORKDIR /home/devops-mcp
USER devops-mcp

ENV PYTHONUNBUFFERED=1

CMD ["devops-mcp"]
