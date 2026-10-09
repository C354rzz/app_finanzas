ARG PYTHON_IMAGE=python:3.12-slim

# --- Etapa css: compila Tailwind con el binario standalone (sin Node) ---
FROM ${PYTHON_IMAGE} AS css
ARG TAILWIND_VERSION=v4.3.3
ADD --chmod=755 https://github.com/tailwindlabs/tailwindcss/releases/download/${TAILWIND_VERSION}/tailwindcss-linux-x64 /usr/local/bin/tailwindcss
WORKDIR /app
COPY static/css/entrada.css static/css/entrada.css
COPY templates templates
COPY apps apps
RUN tailwindcss -i static/css/entrada.css -o static/css/app.css --minify
CMD ["tailwindcss", "-i", "static/css/entrada.css", "-o", "static/css/app.css", "--minify"]

# --- Etapa final ---
FROM ${PYTHON_IMAGE}

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_LINK_MODE=copy \
    PATH="/opt/venv/bin:$PATH"

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --all-groups

COPY . .
COPY --from=css /app/static/css/app.css static/css/app.css
RUN DJANGO_SECRET_KEY=build python manage.py collectstatic --noinput

EXPOSE 8000
ENTRYPOINT ["sh", "/app/docker/entrypoint.sh"]
CMD ["gunicorn", "finanzas.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3"]
