# syntax=docker/dockerfile:1.7

# =========================================================================
# Stage 1 — Build SPA admin (Vite + Vue3). Node chỉ dùng để build, không vào image cuối.
# =========================================================================
FROM node:20-alpine AS web
WORKDIR /web
# Cache layer install: chỉ copy manifest trước.
COPY admin/package.json admin/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY admin/ ./
RUN npm run build   # xuất ra /web/dist


# =========================================================================
# Stage 2 — Cài Python deps vào venv (có toolchain build cho greenlet/pydantic-core).
# =========================================================================
FROM python:3.12-alpine AS deps
# Build deps chỉ tồn tại ở stage này (không vào image cuối).
RUN apk add --no-cache build-base libffi-dev
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip wheel \
 && pip install --no-cache-dir -r requirements.txt \
 # Dọn rác trong venv để nén tối đa: bỏ pyc, test, metadata không cần.
 && find /opt/venv -type d -name '__pycache__' -prune -exec rm -rf {} + \
 && find /opt/venv -type d -name 'tests' -prune -exec rm -rf {} + \
 && find /opt/venv -name '*.pyc' -delete


# =========================================================================
# Stage 3 — Runtime tối giản: chỉ Python slim-alpine + venv + code + admin/dist.
# =========================================================================
FROM python:3.12-alpine AS runtime

# libstdc++ cần cho greenlet/pydantic-core (đã build ở stage deps).
RUN apk add --no-cache libstdc++ \
 && adduser -D -H -u 10001 app

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    WEBHOOK_HOST=0.0.0.0 \
    WEBHOOK_PORT=8000

WORKDIR /app

# venv đã cài sẵn (copy nguyên, không cài lại).
COPY --from=deps /opt/venv /opt/venv
# Mã nguồn backend.
COPY bot/ ./bot/
COPY webhook/ ./webhook/
# SPA đã build (app phục vụ tĩnh từ admin/dist).
COPY --from=web /web/dist ./admin/dist

USER app
EXPOSE 8000

CMD ["python", "-m", "bot.main"]
