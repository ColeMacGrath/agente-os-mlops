# syntax=docker/dockerfile:1
# Imagen del servicio. Los modelos llegan ya entrenados y aprobados por la compuerta
# (carpeta models/ producida por `dvc repro`); la imagen no entrena.
FROM python:3.13-slim
LABEL org.opencontainers.image.title="agente-os-cloud" \
      org.opencontainers.image.source="https://github.com/ColeMacGrath/agente-os-mlops"
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 \
    MODEL_DIR=/app/models PYTHONPATH=/app/src PORT=8000
RUN useradd --create-home --uid 10001 agente
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY src ./src
COPY models ./models
USER agente
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=3s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request,os;urllib.request.urlopen(f'http://127.0.0.1:{os.environ[\"PORT\"]}/health')"
CMD ["sh", "-c", "uvicorn agente_os.api.app:app --host 0.0.0.0 --port ${PORT}"]
