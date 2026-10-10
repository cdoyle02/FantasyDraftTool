FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Build from the repository root:
# docker build -f tools/espn-mcp/Dockerfile .
COPY packages/dvs-engine /build/dvs-engine
COPY apps/api /build/api
COPY tools/espn-mcp /build/espn-mcp
RUN pip install --no-cache-dir /build/dvs-engine /build/api /build/espn-mcp \
    && rm -rf /build

EXPOSE 8000
USER 65534

CMD ["espn-mcp-http"]
