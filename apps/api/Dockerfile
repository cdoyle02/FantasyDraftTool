FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Build from repository root:
# docker build -f apps/api/Dockerfile .
COPY packages/dvs-engine /build/dvs-engine
COPY apps/api /build/api
RUN pip install --no-cache-dir /build/dvs-engine /build/api

EXPOSE 8000
USER 65534

CMD ["uvicorn", "draft_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
