FROM node:22-bookworm-slim AS frontend
WORKDIR /build/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PORT=10000
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends tesseract-ocr tesseract-ocr-eng ca-certificates && rm -rf /var/lib/apt/lists/*
COPY requirements.txt requirements.lock.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY --chown=10001:10001 . ./
COPY --from=frontend --chown=10001:10001 /build/frontend/dist ./frontend/dist
RUN python scripts/package_source.py /app /app/source.zip && groupadd --gid 10001 folio && useradd --uid 10001 --gid folio --no-create-home folio
USER 10001:10001
EXPOSE 10000
CMD ["python", "serve.py"]
