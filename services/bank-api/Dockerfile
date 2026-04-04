FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/services

WORKDIR /app
COPY services/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt
COPY services /app/services
WORKDIR /app/services/bank-api
CMD ["sh", "-c", "alembic -c /app/services/bank-api/alembic.ini upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8002"]
