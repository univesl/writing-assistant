# syntax=docker/dockerfile:1

# ---------------------------------------------------------------------------
# Stage 1: build the React frontend into static assets (frontend/dist)
# ---------------------------------------------------------------------------
FROM node:22-alpine AS frontend-build
WORKDIR /build/frontend

# Install dependencies first so the layer is cached across source-only changes.
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build


# ---------------------------------------------------------------------------
# Stage 2: Python runtime that serves both the API and the built SPA
# ---------------------------------------------------------------------------
FROM python:3.11-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Pandoc is required for DOCX -> Markdown parsing and Markdown -> DOCX export.
RUN apt-get update \
    && apt-get install -y --no-install-recommends pandoc \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Python dependencies (cached separately from application source).
COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install -r /app/backend/requirements.txt

# Application code and operationally-managed resources.
COPY backend/ /app/backend/
COPY skills/   /app/skills/
COPY format/   /app/format/

# The backend mounts ../frontend/dist and serves it on port 9000.
COPY --from=frontend-build /build/frontend/dist /app/frontend/dist

# Absolute runtime paths so they resolve independently of the working dir.
ENV DATABASE_URL=sqlite:////app/data/writing_assistant.db \
    AGENT_CHECKPOINT_PATH=/app/data/agent_checkpoints.sqlite \
    AGENT_SKILLS_ROOT=/app/skills \
    SESSION_FILES_ROOT=/app/session_files

WORKDIR /app/backend

EXPOSE 9000

# Alembic migrations are idempotent and safe alongside Base.metadata.create_all
# (which main.py runs on import). Apply them first, then serve.
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port 9000"]
