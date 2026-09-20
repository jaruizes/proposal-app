FROM python:3.13-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DOCUMENT_RENDERER_TEMPLATE_DIR=/opt/document-renderer/templates \
    HOME=/tmp/renderer-home

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
      libreoffice-core \
      libreoffice-writer \
      fontconfig \
      fonts-dejavu-core \
      fonts-liberation && \
    rm -rf /var/lib/apt/lists/* && \
    useradd --create-home --uid 10001 renderer && \
    mkdir -p /app /opt/document-renderer/templates /tmp/renderer-home && \
    chown -R renderer:renderer /app /opt/document-renderer /tmp/renderer-home

WORKDIR /app
COPY document-renderer/pyproject.toml /app/pyproject.toml
RUN pip install --no-cache-dir .

COPY --chown=renderer:renderer document-renderer/app /app/app
COPY --chown=renderer:renderer document-renderer/templates /opt/document-renderer/templates

USER 10001:10001
EXPOSE 8090

HEALTHCHECK --interval=10s --timeout=3s --retries=10 CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8090/health/ready')"

ENTRYPOINT ["uvicorn","app.main:app","--host","0.0.0.0","--port","8090"]
