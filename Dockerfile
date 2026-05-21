FROM node:22-alpine AS webui-builder
WORKDIR /app/webui
COPY webui/package*.json ./
RUN npm ci
COPY webui/ ./
RUN npm run build

FROM python:3.12-slim AS runtime
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app/packages/common:/app/packages/sdk:/app/packages/cli:/app/apps/server \
    BLACKBOX_DATA_DIR=/data \
    BLACKBOX_ARTIFACT_STORAGE=local

WORKDIR /app
COPY pyproject.toml ./
COPY packages ./packages
COPY apps ./apps
RUN pip install --no-cache-dir ".[s3,postgres]"

COPY webui ./webui
COPY --from=webui-builder /app/webui/dist ./webui/dist

EXPOSE 8000
CMD ["python", "-m", "uvicorn", "blackbox_server.main:app", "--host", "0.0.0.0", "--port", "8000"]
