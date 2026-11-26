# Imagen de producción para Railway.
FROM python:3.13-slim

# No genera .pyc y no almacena en búfer los logs (así aparecen al instante en Railway).
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    APP_ENV=production

WORKDIR /srv

# Se copia solo lo necesario para instalar. Sin extras "dev": no hace falta pytest ni ruff.
COPY pyproject.toml ./
COPY app ./app
RUN pip install --no-cache-dir .

# Migraciones: las ejecuta el propio CMD al arrancar (ver más abajo).
COPY alembic.ini ./
COPY alembic ./alembic

# Usuario sin privilegios: si alguien explota la app, no es root dentro del contenedor.
RUN useradd --create-home appuser
USER appuser

# Railway pone UN proxy delante de la app: la IP real del cliente es la última de
# X-Forwarded-For (ver app/core/client_ip.py). Con otro proxy delante, súbelo a 2.
ENV TRUSTED_PROXY_HOPS=1

# Railway inyecta $PORT; 8000 es el valor por defecto para probar en local.
# Forma "sh -c" para que se expanda la variable. exec reemplaza el shell por uvicorn,
# así recibe las señales de apagado correctamente.
# Antes de arrancar se aplican las migraciones (si ya están al día, no hace nada). Así la app
# nunca arranca sin sus tablas, aunque el pre-deploy de la plataforma no se ejecute. Si la
# migración falla, el contenedor termina y no se arranca el servidor.
# --no-proxy-headers: uvicorn NO reescribe la IP del cliente; con --forwarded-allow-ips='*' se
# quedaría con la primera de X-Forwarded-For, que escribe el propio cliente.
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --no-proxy-headers"]
