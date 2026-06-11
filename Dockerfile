FROM python:3.12-slim

WORKDIR /app

COPY . .

RUN pip install --no-cache-dir .

ENV PYTHONUNBUFFERED=1

CMD ["devops-mcp"]
