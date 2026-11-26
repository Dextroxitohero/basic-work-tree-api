# Imagen de producción para Railway.
FROM python:3.13-slim

# No genera .pyc y no almacena en búfer los logs (así aparecen al instante en Railway).
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /srv

# Se copia solo lo necesario para instalar. Sin extras "dev": no hace falta pytest ni ruff.
COPY pyproject.toml ./
COPY app ./app
RUN pip install --no-cache-dir .

# Migraciones (las ejecuta Railway como pre-deploy command, ver railway.json).
COPY alembic.ini ./
COPY alembic ./alembic

# Usuario sin privilegios: si alguien explota la app, no es root dentro del contenedor.
RUN useradd --create-home appuser
USER appuser

# Railway inyecta $PORT; 8000 es el valor por defecto para probar en local.
# Forma "sh -c" para que se expanda la variable. exec reemplaza el shell por uvicorn,
# así recibe las señales de apagado correctamente.
# --proxy-headers: detrás del proxy de Railway, request.client es la IP real del cliente (el
# límite de intentos de login la necesita).
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*'"]
