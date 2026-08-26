# Imagen de la aplicación web de Voceo.
#
#   docker build -t voceo .
#   docker run -p 8080:8080 -e VOCEO_CLAVE=lacontraseña voceo
#
# ffmpeg va dentro de la imagen: es lo que monta la campanilla, los silencios,
# las repeticiones y la normalización de volumen.

FROM python:3.12-slim

RUN apt-get update \
 && apt-get install -y --no-install-recommends ffmpeg \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Primero los metadatos: así la capa de dependencias se reaprovecha entre
# compilaciones mientras no cambien.
COPY pyproject.toml README.md LICENSE ./
COPY voceo ./voceo
RUN pip install --no-cache-dir ".[web]"

# El servidor no guarda nada, así que puede correr sin permisos de escritura.
RUN useradd --create-home --uid 10001 voceo
USER voceo

ENV PORT=8080 \
    PYTHONUNBUFFERED=1
EXPOSE 8080

# Dos procesos con varios hilos cada uno: la síntesis espera por la red, no
# por la CPU. El tiempo de espera es holgado para los lotes grandes.
CMD exec gunicorn \
      --bind ":$PORT" \
      --workers 2 \
      --threads 8 \
      --timeout 300 \
      --access-logfile - \
      "voceo.web.app:crear_app()"
