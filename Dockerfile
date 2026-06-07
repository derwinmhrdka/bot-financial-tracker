FROM python:3.12-slim-bookworm

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN groupadd --gid 1000 app \
    && useradd --uid 1000 --gid app --shell /bin/bash --create-home app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY track.py .
COPY tracker/ ./tracker/

RUN mkdir -p /app/data /app/secrets \
    && chown -R app:app /app

USER app

CMD ["python", "-m", "tracker.telegram_bot"]
