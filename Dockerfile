FROM node:22-bookworm-slim AS frontend
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json ./frontend/
RUN --mount=type=secret,id=proxy_ca if [ -f /run/secrets/proxy_ca ]; then export NODE_EXTRA_CA_CERTS=/run/secrets/proxy_ca; fi; npm --prefix frontend ci --omit=dev
COPY frontend ./frontend

FROM python:3.12-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends tesseract-ocr && rm -rf /var/lib/apt/lists/*
COPY backend/requirements.txt backend/requirements-analysis.txt ./backend/
RUN --mount=type=secret,id=proxy_ca if [ -f /run/secrets/proxy_ca ]; then export PIP_CERT=/run/secrets/proxy_ca; fi; pip install --no-cache-dir -r backend/requirements-analysis.txt
COPY backend ./backend
COPY --from=frontend /app/frontend ./frontend
COPY docs ./docs
COPY challenges/1-referral-intake/criteria ./challenges/1-referral-intake/criteria
RUN chmod -R a+rX /app && useradd --create-home careward
USER careward
EXPOSE 10000
CMD ["python", "-m", "uvicorn", "backend.app:app", "--host", "0.0.0.0", "--port", "10000", "--no-access-log"]
