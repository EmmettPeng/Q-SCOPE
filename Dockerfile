FROM node:22-alpine@sha256:16e22a550f3863206a3f701448c45f7912c6896a62de43add43bb9c86130c3e2 AS frontend-build
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim@sha256:57cd7c3a7a273101a6485ba99423ee568157882804b1124b4dd04266317710de
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       hmmer=3.4+dfsg-2+b2 \
       prodigal=1:2.6.3-6+b1 \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system qscn \
    && useradd --system --gid qscn --home-dir /app --shell /usr/sbin/nologin qscn
WORKDIR /app
COPY backend/requirements.txt backend/requirements.lock ./backend/
RUN pip install --no-cache-dir -r backend/requirements.lock
COPY backend/qscn ./qscn
COPY --from=frontend-build /frontend/dist ./frontend-dist
COPY databases ./database-source
RUN mkdir -p /app/database-runtime /data \
    && cp /app/database-source/*.hmm /app/database-source/*.json /app/database-runtime/ \
    && hmmpress /app/database-runtime/QSPdatabase.hmm \
    && hmmpress /app/database-runtime/kegg_m02024.hmm \
    && chown -R qscn:qscn /data /app/database-runtime \
    && chmod -R a-w /app/database-source /app/database-runtime
ARG QSCN_BUILD_REVISION=unknown
ARG QSCN_BUILD_TIMESTAMP=unknown
LABEL org.opencontainers.image.title="QSCN" \
      org.opencontainers.image.version="0.3.1" \
      org.opencontainers.image.revision="${QSCN_BUILD_REVISION}" \
      org.opencontainers.image.created="${QSCN_BUILD_TIMESTAMP}" \
      org.opencontainers.image.licenses="Apache-2.0"
ENV QSCN_BUILD_REVISION=${QSCN_BUILD_REVISION} QSCN_BUILD_TIMESTAMP=${QSCN_BUILD_TIMESTAMP}
USER qscn:qscn
EXPOSE 8000
CMD ["uvicorn", "qscn.api:app", "--host", "0.0.0.0", "--port", "8000"]
