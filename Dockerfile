FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    MOTIONJSON_BACKEND_DB=/data/backend.sqlite \
    MOTIONJSON_STORAGE_ROOT=/data/storage

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt pyproject.toml README.md ./
COPY src ./src
COPY docs ./docs
COPY examples ./examples
COPY packages ./packages

RUN pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir -e .

EXPOSE 8765

CMD ["python", "-m", "motionjson.cli", "backend", "serve-api", "--host", "0.0.0.0", "--port", "8765"]
