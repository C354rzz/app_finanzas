# Plan 1 — Fundación: Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Dejar corriendo en Docker la base de la app: Django + PostgreSQL, CI, usuario por email, multi-hogar, catálogos (personas, domicilios, categorías, conceptos, cuentas) en el admin y el motor de cálculos (`apps/calculos`) probado contra los valores reales del Excel.

**Architecture:** Monolito Django modular (`apps/core`, `apps/catalogos`, `apps/calculos`). `calculos` es Python puro con `Decimal`, sin importar Django. Todo modelo de negocio hereda de `ModeloDeHogar` (tenant). Todo se ejecuta dentro de Docker Compose (`web` + `db`); el código del host se monta en `/app` durante el desarrollo.

**Tech Stack:** Python 3.12, Django 5.2 LTS, PostgreSQL 17, psycopg 3, django-environ, gunicorn, whitenoise, uv, pytest + pytest-django + factory-boy, ruff, Docker Compose v5, GitHub Actions.

**Spec:** `docs/DEF.md`, `docs/ARQUITECTURA.md`, `docs/modelo-datos.dbml` (v1.0, aprobados 2026-10-09).

### Hoja de ruta (este es el plan 1 de 5)
| Plan | Contenido | Requisitos del DEF |
|---|---|---|
| **1 — Fundación (este)** | Docker, CI, usuario, hogar, catálogos (admin), motor de cálculos RN-01..08, RN-10 | ACC-01 y CAT-01..05 (vía admin), ACC-02 (12 categorías; conceptos y tasas del Excel → plan 5), ACC-03, RN-01..08, RN-10, RNF-05/08/09 |
| 2 — Operación diaria | Login/UI base (Tailwind, HTMX), movimientos, presupuesto (plantilla y mes), tablero, catálogos en UI | MOV-*, PRE-*, TAB-*, RN-11..15 parcial |
| 3 — Planeación | Metas, deudas, patrimonio, simulador (UI sobre `calculos`), tasas de mercado | MET-*, DEU-*, PAT-*, SIM-* |
| 4 — Importación IA | Django-Q2, worker, pypdf, Claude API, reglas, duplicados, revisión | IMP-*, RN-11, RN-12 |
| 5 — Operación | PWA, Tailscale, respaldo/restauración, importación inicial desde Excel | ACC-04, DAT-*, RNF-01/06 |

## Global Constraints

- Python **3.12**; Django **>=5.2,<5.3**; PostgreSQL **17**.
- Dinero: `Decimal`, `DecimalField(max_digits=12, decimal_places=2)`. **Nunca `float`.** Tasas: fracción, `DecimalField(max_digits=7, decimal_places=4)` (0.2500 = 25%).
- Redondeo a 2 decimales **solo al mostrar o al comparar en pruebas** (`apps.calculos.comun.redondear`).
- Nombres de dominio en **español** (modelos, campos, funciones). Mensajes de error en español.
- `LANGUAGE_CODE = "es-mx"`, `TIME_ZONE = "America/Monterrey"`, `USE_TZ = True`.
- `apps/calculos/` **no importa nada de Django**.
- Todo modelo de negocio hereda de `apps.core.models.ModeloDeHogar` (excepto catálogos globales como `TasaMercado`).
- **Ningún dato personal en el repo:** nada de `2026/`, PDFs, Excel ni `.env`. Los fixtures de prueba son sintéticos o anónimos.
- La app y el repo git viven en **`Finanzas\app_finanzas\`**. Todos los comandos se ejecutan desde PowerShell en esa carpeta y **dentro de Docker** (`docker compose run --rm web ...`). No crear `.venv/` en el repo. Los datos personales (`..\2026\`) y la memoria del proyecto (`..\CLAUDE.md`) quedan **fuera** del repo.
- Finales de línea LF (ya forzado por `.gitattributes`).
- Cada commit termina con la línea: `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`

## Review Focus

1. **Email con distinta capitalización** (`Julio@Example.com` vs `julio@example.com`) → es el mismo usuario al crear y al iniciar sesión, no un duplicado. *Prueba en Task 6.*
2. **Relaciones entre hogares distintos** (un concepto que apunta a una categoría o persona de otro hogar) → `ValidationError` al validar, nunca se guarda en silencio. *Prueba en Task 8.*
3. **Pago anticipado mayor al saldo** en el simulador → el crédito termina en saldo 0 ese mes; nunca saldo negativo ni meses de más. *Prueba en Task 4.*
4. **Entradas degeneradas** (tasa 0%, meses 0, montos negativos, % de ahorro > 100%) → resultado correcto sin división entre cero, o `ValueError` con mensaje claro. *Pruebas en Tasks 3, 4 y 5.*
5. **Tarjeta sin línea de crédito o con saldo a favor (negativo)** → el % de uso no truena (devuelve `None` si no hay línea) y el saldo a favor cuenta como 0 de deuda. *Prueba en Task 5.*

---

## Estructura de archivos

```
Finanzas\app_finanzas\                (raíz del repo; ya contiene .gitignore, .gitattributes y docs\)
├── .dockerignore                      (T1) excluye archivos sensibles de la imagen
├── .env.example                       (T1)
├── README.md                          (T1) comandos de desarrollo
├── pyproject.toml / uv.lock           (T1; T2 añade config de ruff)
├── manage.py                          (T1)
├── docker\Dockerfile                  (T1)
├── docker\entrypoint.sh               (T1; T6 añade migrate)
├── docker-compose.yml                 (T1) web + db
├── docker-compose.override.yml        (T1) modo desarrollo
├── .github\workflows\ci.yml           (T2)
├── finanzas\  settings.py urls.py wsgi.py vistas.py __init__.py   (T1; T6/T7/T8 modifican settings)
├── apps\__init__.py                   (T3)
├── apps\calculos\  __init__.py comun.py presupuesto.py metas.py credito.py deudas.py   (T3–T5)
├── apps\core\  apps.py models.py admin.py middleware.py servicios.py migrations\   (T6–T8)
├── apps\catalogos\  apps.py models.py admin.py servicios.py management\commands\crear_hogar.py migrations\   (T8–T9)
└── tests\
    ├── conftest.py                    (T7)
    ├── test_salud.py                  (T1)
    ├── calculos\ test_calc_presupuesto.py test_calc_metas.py test_calc_credito.py test_calc_deudas.py
    ├── core\ test_core_usuario.py test_core_hogar.py
    └── catalogos\ test_catalogos_modelos.py test_catalogos_siembra.py
```

Los nombres de archivo de prueba son únicos a propósito (pytest con `--import-mode=importlib`, sin `__init__.py` en `tests/`).

---

### Task 1: Esqueleto Docker + Django con endpoint de salud

**Files:**
- Create: `pyproject.toml`, `uv.lock` (generado), `.dockerignore`, `.env.example`, `README.md`, `manage.py`
- Create: `docker/Dockerfile`, `docker/entrypoint.sh`, `docker-compose.yml`, `docker-compose.override.yml`
- Create: `finanzas/__init__.py`, `finanzas/settings.py`, `finanzas/urls.py`, `finanzas/wsgi.py`, `finanzas/vistas.py`
- Test: `tests/test_salud.py`

**Interfaces:**
- Produces: proyecto Django `finanzas`; URL `/salud/` (nombre `salud`) → `{"estado": "ok"}`; servicio Compose `web` (puerto 8000) y `db`; comando de pruebas `docker compose run --rm web pytest`.

- [ ] **Step 1: Crear `pyproject.toml`**

```toml
[project]
name = "finanzas"
version = "0.1.0"
description = "App de finanzas familiares"
requires-python = ">=3.12,<3.13"
dependencies = [
    "django>=5.2,<5.3",
    "psycopg[binary]>=3.2",
    "django-environ>=0.12",
    "gunicorn>=23",
    "whitenoise>=6.8",
]

[dependency-groups]
dev = [
    "pytest>=8.3",
    "pytest-django>=4.9",
    "pytest-cov>=6.0",
    "factory-boy>=3.3",
    "ruff>=0.8",
]

[tool.uv]
package = false

[tool.pytest.ini_options]
DJANGO_SETTINGS_MODULE = "finanzas.settings"
testpaths = ["tests"]
python_files = ["test_*.py"]
addopts = "-q --import-mode=importlib"
```

- [ ] **Step 2: Generar `uv.lock` con Docker (sin instalar uv en Windows)**

Run (PowerShell, en `Finanzas\app_finanzas\`):
```powershell
docker run --rm -v "${PWD}:/app" -w /app ghcr.io/astral-sh/uv:python3.12-bookworm-slim uv lock
```
Expected: se crea `uv.lock`; la salida termina con `Resolved N packages`.

- [ ] **Step 3: Crear `.dockerignore`, `.env.example` y copiar a `.env`**

`.dockerignore`:
```
.git
.github
.env
.env.*
20*/
media/
backups/
staticfiles/
**/__pycache__
.pytest_cache
.ruff_cache
*.pdf
*.xlsx
*.zip
```

`.env.example`:
```
DJANGO_DEBUG=1
DJANGO_SECRET_KEY=cambia-esto-por-una-clave-larga-y-aleatoria
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1
DATABASE_URL=postgres://finanzas:finanzas@db:5432/finanzas
POSTGRES_PASSWORD=finanzas
```

Run: `Copy-Item .env.example .env`

- [ ] **Step 4: Crear el proyecto Django**

`manage.py`:
```python
#!/usr/bin/env python
import os
import sys


def main():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "finanzas.settings")
    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
```

`finanzas/__init__.py`: archivo vacío.

`finanzas/wsgi.py`:
```python
import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "finanzas.settings")
application = get_wsgi_application()
```

`finanzas/settings.py`:
```python
"""Configuración de Django para la app de finanzas familiares."""

from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent
env = environ.Env(DJANGO_DEBUG=(bool, False))

SECRET_KEY = env("DJANGO_SECRET_KEY", default="solo-para-desarrollo-no-usar-en-produccion")
DEBUG = env("DJANGO_DEBUG")
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])
CSRF_TRUSTED_ORIGINS = env.list("DJANGO_CSRF_TRUSTED_ORIGINS", default=[])

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "finanzas.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "finanzas.wsgi.application"

DATABASES = {
    "default": env.db("DATABASE_URL", default="postgres://finanzas:finanzas@db:5432/finanzas"),
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "es-mx"
TIME_ZONE = "America/Monterrey"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedStaticFilesStorage"},
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
```

`finanzas/vistas.py`:
```python
from django.db import connection
from django.http import JsonResponse


def salud(request):
    """Responde ok si la app y la base de datos están disponibles."""
    connection.ensure_connection()
    return JsonResponse({"estado": "ok"})
```

`finanzas/urls.py`:
```python
from django.contrib import admin
from django.urls import path

from finanzas.vistas import salud

urlpatterns = [
    path("admin/", admin.site.urls),
    path("salud/", salud, name="salud"),
]
```

- [ ] **Step 5: Crear la imagen y Compose**

`docker/entrypoint.sh`:
```sh
#!/bin/sh
set -e
exec "$@"
```

`docker/Dockerfile`:
```dockerfile
FROM python:3.12-slim

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
RUN DJANGO_SECRET_KEY=build python manage.py collectstatic --noinput

EXPOSE 8000
ENTRYPOINT ["sh", "/app/docker/entrypoint.sh"]
CMD ["gunicorn", "finanzas.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3"]
```

`docker-compose.yml`:
```yaml
name: finanzas

services:
  db:
    image: postgres:17
    environment:
      POSTGRES_DB: finanzas
      POSTGRES_USER: finanzas
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-finanzas}
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U finanzas -d finanzas"]
      interval: 5s
      timeout: 5s
      retries: 10

  web:
    build:
      context: .
      dockerfile: docker/Dockerfile
    env_file:
      - path: .env
        required: false
    depends_on:
      db:
        condition: service_healthy
    ports:
      - "8000:8000"
    volumes:
      - media:/app/media

volumes:
  pgdata:
  media:
```

`docker-compose.override.yml` (desarrollo; Compose lo aplica automáticamente):
```yaml
services:
  web:
    command: python manage.py runserver 0.0.0.0:8000
    environment:
      DJANGO_DEBUG: "1"
    volumes:
      - .:/app
```

- [ ] **Step 6: Escribir la prueba que falla**

`tests/test_salud.py`:
```python
import pytest


@pytest.mark.django_db
def test_salud_responde_ok(client):
    respuesta = client.get("/salud/")

    assert respuesta.status_code == 200
    assert respuesta.json() == {"estado": "ok"}
```

- [ ] **Step 7: Construir y correr la prueba**

Run:
```powershell
docker compose build
docker compose run --rm web pytest tests/test_salud.py -v
```
Expected: `1 passed`. (Si falla con "relation does not exist" o conexión, revisar que `db` esté healthy: `docker compose ps`.)

- [ ] **Step 8: Verificar el servidor en el navegador**

Run: `docker compose up -d` y abrir `http://localhost:8000/salud/`
Expected: `{"estado": "ok"}`. Luego `docker compose down` (sin `-v`).

- [ ] **Step 9: Crear `README.md`**

```markdown
# Finanzas familiares

App web (Django + HTMX + PostgreSQL) que reemplaza el planeador en Excel.
Documentación: `docs/ARQUITECTURA.md`, `docs/DEF.md`, `docs/modelo-datos.dbml`.

## Desarrollo (PowerShell, en `Finanzas\app_finanzas\`)

| Acción | Comando |
|---|---|
| Primera vez | `Copy-Item .env.example .env` y `docker compose build` |
| Levantar | `docker compose up -d` → http://localhost:8000 |
| Pruebas | `docker compose run --rm web pytest` |
| Lint | `docker compose run --rm web ruff check .` |
| Formato | `docker compose run --rm web ruff format .` |
| Migraciones | `docker compose run --rm web python manage.py makemigrations` |
| Shell Django | `docker compose run --rm web python manage.py shell` |
| Cambié dependencias | `docker run --rm -v "${PWD}:/app" -w /app ghcr.io/astral-sh/uv:python3.12-bookworm-slim uv lock` y `docker compose build` |
| Detener | `docker compose down` (con `-v` **borra la base de datos**) |

⚠️ Los datos personales viven fuera de esta carpeta (`..\2026\`). Nunca copies PDFs ni el Excel aquí.
```

- [ ] **Step 10: Commit**

```powershell
git add pyproject.toml uv.lock .dockerignore .env.example README.md manage.py docker docker-compose.yml docker-compose.override.yml finanzas tests/test_salud.py
git status --short   # confirmar que .env NO aparece
git commit -m "feat: esqueleto Django + Postgres en Docker con endpoint de salud" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: Lint (ruff) e integración continua en GitHub Actions

**Files:**
- Modify: `pyproject.toml` (añadir `[tool.ruff]`)
- Create: `.github/workflows/ci.yml`

**Interfaces:**
- Consumes: `pyproject.toml`, `uv.lock`, `docker/Dockerfile` (Task 1).
- Produces: `ruff check .` y `ruff format --check .` en verde; workflow `CI` con jobs `pruebas` e `imagen`.

- [ ] **Step 1: Añadir configuración de ruff al final de `pyproject.toml`**

```toml
[tool.ruff]
line-length = 100
target-version = "py312"
extend-exclude = ["**/migrations/*"]

[tool.ruff.lint]
select = ["E", "F", "W", "I", "UP", "B", "DJ", "SIM"]
```

- [ ] **Step 2: Correr ruff (debe pasar o mostrar lo que hay que formatear)**

Run:
```powershell
docker compose run --rm web ruff format .
docker compose run --rm web ruff check .
```
Expected: `All checks passed!`. Si `ruff check` reporta algo, corregirlo en el archivo indicado y repetir.

- [ ] **Step 3: Crear `.github/workflows/ci.yml`**

```yaml
name: CI

on:
  push:
  pull_request:

jobs:
  pruebas:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:17
        env:
          POSTGRES_DB: finanzas
          POSTGRES_USER: finanzas
          POSTGRES_PASSWORD: finanzas
        ports:
          - 5432:5432
        options: >-
          --health-cmd "pg_isready -U finanzas -d finanzas"
          --health-interval 5s
          --health-timeout 5s
          --health-retries 10
    env:
      DATABASE_URL: postgres://finanzas:finanzas@localhost:5432/finanzas
      DJANGO_SECRET_KEY: ci-no-secreto
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v6
        with:
          python-version: "3.12"
      - run: uv sync --frozen --all-groups
      - run: uv run ruff check .
      - run: uv run ruff format --check .
      - run: uv run pytest --cov=apps --cov-report=term-missing

  imagen:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: docker build -f docker/Dockerfile -t finanzas:ci .
```

- [ ] **Step 4: Validar que la suite y el YAML son correctos localmente**

Run:
```powershell
docker compose run --rm web pytest
docker run --rm -v "${PWD}:/w" -w /w mikefarah/yq '.jobs | keys' .github/workflows/ci.yml
```
Expected: `1 passed` y la lista `- pruebas` / `- imagen` (si el YAML fuera inválido, yq muestra el error de sintaxis). (El workflow correrá en GitHub cuando el usuario cree el remoto y haga push; no hay remoto todavía.)

- [ ] **Step 5: Commit**

```powershell
git add pyproject.toml .github/workflows/ci.yml
git commit -m "ci: ruff y pytest con Postgres en GitHub Actions" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: Cálculos de presupuesto (RN-01 a RN-04)

**Files:**
- Create: `apps/__init__.py` (vacío), `apps/calculos/__init__.py` (vacío), `apps/calculos/comun.py`, `apps/calculos/presupuesto.py`
- Test: `tests/calculos/test_calc_presupuesto.py`

**Interfaces:**
- Produces:
  - `apps.calculos.comun`: `CERO: Decimal`, `redondear(valor: Decimal, decimales: int = 2) -> Decimal` (ROUND_HALF_UP).
  - `apps.calculos.presupuesto`: constantes `MENSUAL = "mensual"`, `ANUAL = "anual"`; dataclasses `LineaIngreso(monto: Decimal, es_fijo: bool = True)`, `LineaGasto(monto: Decimal, periodicidad: str = MENSUAL, es_fijo=False, con_tarjeta=False, es_hormiga=False)` con método `monto_mensual() -> Decimal`; dataclass `ResumenPresupuesto` (campos abajo); función `resumir_presupuesto(ingresos: Iterable[LineaIngreso], gastos: Iterable[LineaGasto], porcentaje_ahorro: Decimal) -> ResumenPresupuesto`.

- [ ] **Step 1: Escribir las pruebas que fallan**

`tests/calculos/test_calc_presupuesto.py`:
```python
from decimal import Decimal as D

import pytest

from apps.calculos.comun import redondear
from apps.calculos.presupuesto import (
    ANUAL,
    LineaGasto,
    LineaIngreso,
    resumir_presupuesto,
)


def g(monto, fijo=False, tarjeta=False, hormiga=False):
    return LineaGasto(monto=D(monto), es_fijo=fijo, con_tarjeta=tarjeta, es_hormiga=hormiga)


# Renglones del presupuesto del Excel 2026 del usuario (sin nombres), por categoría.
GASTOS_EXCEL = [
    # Casa
    g("200", fijo=True), g("100"), g("1500", fijo=True), g("1100", fijo=True),
    g("500", fijo=True), g("500", fijo=True), g("100", fijo=True),
    # Comida
    g("3000", fijo=True), g("3000", fijo=True), g("1600", fijo=True), g("2000", fijo=True),
    g("600", hormiga=True), g("400", hormiga=True),
    # Familia
    g("4641", fijo=True), g("800", fijo=True),
    # Transporte
    g("1400", fijo=True), g("1000", fijo=True),
    # Deudas
    g("1500", fijo=True), g("2000", fijo=True),
    # Salud
    g("1000", fijo=True),
    # Suscripciones
    g("239", tarjeta=True, hormiga=True), g("10", tarjeta=True), g("49", tarjeta=True),
    g("196", fijo=True),
    # Entretenimiento
    g("500", hormiga=True),
    # Otros
    g("300", fijo=True), g("500", tarjeta=True, hormiga=True), g("500", tarjeta=True, hormiga=True),
]
INGRESOS_EXCEL = [LineaIngreso(monto=D("32977.52"), es_fijo=True)]


def test_reproduce_los_valores_del_excel():
    r = resumir_presupuesto(INGRESOS_EXCEL, GASTOS_EXCEL, D("0.05"))

    assert r.ingresos_fijos == D("32977.52")
    assert r.ingresos_variables == D("0")
    assert r.ingresos_totales == D("32977.52")
    assert r.gastos_totales == D("29235")
    assert r.gastos_fijos == D("26337")
    assert r.gastos_variables == D("2898")
    assert r.disponible == D("3742.52")
    assert r.meta_ahorro == D("1648.876")
    assert r.presupuesto_hormiga == D("2739")
    assert redondear(r.maximo_diario_hormiga) == D("91.30")
    assert r.recorte_necesario is None
    assert r.gasto_con_tarjeta == D("1298")


def test_recorte_necesario_cuando_el_disponible_no_alcanza_la_meta():
    r = resumir_presupuesto(
        [LineaIngreso(D("10000"))], [g("9500")], D("0.10")
    )

    assert r.disponible == D("500")
    assert r.meta_ahorro == D("1000")
    assert r.recorte_necesario == D("500")


def test_gasto_anual_se_prorratea_entre_12_en_todos_los_totales():
    anual = LineaGasto(monto=D("1200"), periodicidad=ANUAL, es_fijo=True, es_hormiga=True)

    assert anual.monto_mensual() == D("100")
    r = resumir_presupuesto([LineaIngreso(D("1000"))], [anual], D("0"))
    assert r.gastos_totales == D("100")
    assert r.gastos_fijos == D("100")
    assert r.presupuesto_hormiga == D("100")


def test_ingresos_variables_se_separan_de_fijos():
    r = resumir_presupuesto(
        [LineaIngreso(D("1000"), es_fijo=True), LineaIngreso(D("250"), es_fijo=False)], [], D("0")
    )

    assert r.ingresos_fijos == D("1000")
    assert r.ingresos_variables == D("250")
    assert r.ingresos_totales == D("1250")


def test_presupuesto_vacio_da_ceros():
    r = resumir_presupuesto([], [], D("0.10"))

    assert r.ingresos_totales == D("0")
    assert r.gastos_totales == D("0")
    assert r.maximo_diario_hormiga == D("0")
    assert r.recorte_necesario is None


def test_periodicidad_desconocida_es_error():
    with pytest.raises(ValueError, match="Periodicidad"):
        LineaGasto(monto=D("10"), periodicidad="semanal").monto_mensual()


@pytest.mark.parametrize("porcentaje", [D("-0.01"), D("1.01")])
def test_porcentaje_de_ahorro_fuera_de_rango_es_error(porcentaje):
    with pytest.raises(ValueError, match="porcentaje"):
        resumir_presupuesto([], [], porcentaje)


def test_montos_negativos_son_error():
    with pytest.raises(ValueError, match="negativ"):
        resumir_presupuesto([LineaIngreso(D("-1"))], [], D("0"))
    with pytest.raises(ValueError, match="negativ"):
        resumir_presupuesto([], [g("-5")], D("0"))
```

- [ ] **Step 2: Correr las pruebas para verificar que fallan**

Run: `docker compose run --rm web pytest tests/calculos/test_calc_presupuesto.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'apps'`.

- [ ] **Step 3: Implementar**

`apps/__init__.py` y `apps/calculos/__init__.py`: vacíos.

`apps/calculos/comun.py`:
```python
"""Utilidades compartidas por los cálculos financieros (sin dependencias de Django)."""

from decimal import ROUND_HALF_UP, Decimal

CERO = Decimal("0")


def redondear(valor: Decimal, decimales: int = 2) -> Decimal:
    """Redondea al estilo comercial (0.005 → 0.01). Usar solo para mostrar o comparar."""
    return valor.quantize(Decimal(1).scaleb(-decimales), rounding=ROUND_HALF_UP)
```

`apps/calculos/presupuesto.py`:
```python
"""Reglas RN-01 a RN-04 del DEF: resumen del presupuesto mensual."""

from collections.abc import Iterable
from dataclasses import dataclass
from decimal import Decimal

from apps.calculos.comun import CERO

MENSUAL = "mensual"
ANUAL = "anual"
DIAS_POR_MES = Decimal("30")


@dataclass(frozen=True)
class LineaIngreso:
    monto: Decimal
    es_fijo: bool = True


@dataclass(frozen=True)
class LineaGasto:
    monto: Decimal
    periodicidad: str = MENSUAL
    es_fijo: bool = False
    con_tarjeta: bool = False
    es_hormiga: bool = False

    def monto_mensual(self) -> Decimal:
        """RN-03: un gasto anual cuenta como monto / 12 en todos los totales."""
        if self.periodicidad == MENSUAL:
            return self.monto
        if self.periodicidad == ANUAL:
            return self.monto / 12
        raise ValueError(f"Periodicidad desconocida: {self.periodicidad!r}")


@dataclass(frozen=True)
class ResumenPresupuesto:
    ingresos_fijos: Decimal
    ingresos_variables: Decimal
    ingresos_totales: Decimal
    gastos_fijos: Decimal
    gastos_variables: Decimal
    gastos_totales: Decimal
    disponible: Decimal
    meta_ahorro: Decimal
    presupuesto_hormiga: Decimal
    maximo_diario_hormiga: Decimal
    recorte_necesario: Decimal | None
    gasto_con_tarjeta: Decimal


def resumir_presupuesto(
    ingresos: Iterable[LineaIngreso],
    gastos: Iterable[LineaGasto],
    porcentaje_ahorro: Decimal,
) -> ResumenPresupuesto:
    """Calcula RN-01 (totales), RN-02 (meta de ahorro) y RN-04 (gastos hormiga)."""
    if not CERO <= porcentaje_ahorro <= 1:
        raise ValueError("El porcentaje de ahorro debe estar entre 0 y 1")
    ingresos = list(ingresos)
    gastos = list(gastos)
    if any(linea.monto < 0 for linea in [*ingresos, *gastos]):
        raise ValueError("Los montos no pueden ser negativos")

    ingresos_fijos = sum((i.monto for i in ingresos if i.es_fijo), CERO)
    ingresos_totales = sum((i.monto for i in ingresos), CERO)
    gastos_totales = sum((x.monto_mensual() for x in gastos), CERO)
    gastos_fijos = sum((x.monto_mensual() for x in gastos if x.es_fijo), CERO)
    hormiga = sum((x.monto_mensual() for x in gastos if x.es_hormiga), CERO)
    con_tarjeta = sum((x.monto_mensual() for x in gastos if x.con_tarjeta), CERO)

    disponible = ingresos_totales - gastos_totales
    meta_ahorro = ingresos_totales * porcentaje_ahorro
    faltante = disponible - meta_ahorro

    return ResumenPresupuesto(
        ingresos_fijos=ingresos_fijos,
        ingresos_variables=ingresos_totales - ingresos_fijos,
        ingresos_totales=ingresos_totales,
        gastos_fijos=gastos_fijos,
        gastos_variables=gastos_totales - gastos_fijos,
        gastos_totales=gastos_totales,
        disponible=disponible,
        meta_ahorro=meta_ahorro,
        presupuesto_hormiga=hormiga,
        maximo_diario_hormiga=hormiga / DIAS_POR_MES,
        recorte_necesario=None if faltante >= 0 else -faltante,
        gasto_con_tarjeta=con_tarjeta,
    )
```

- [ ] **Step 4: Correr las pruebas para verificar que pasan**

Run: `docker compose run --rm web pytest tests/calculos/test_calc_presupuesto.py -v`
Expected: `9 passed`.

- [ ] **Step 5: Lint y commit**

```powershell
docker compose run --rm web ruff format apps tests
docker compose run --rm web ruff check .
git add apps/__init__.py apps/calculos tests/calculos/test_calc_presupuesto.py
git commit -m "feat(calculos): resumen de presupuesto RN-01..RN-04 verificado contra el Excel" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: Cálculos de metas de ahorro (RN-05) y amortización de créditos (RN-07)

**Files:**
- Create: `apps/calculos/metas.py`, `apps/calculos/credito.py`
- Test: `tests/calculos/test_calc_metas.py`, `tests/calculos/test_calc_credito.py`

**Interfaces:**
- Consumes: `apps.calculos.comun.CERO`, `redondear` (Task 3).
- Produces:
  - `apps.calculos.metas.aporte_mensual_meta(monto_objetivo: Decimal, ahorro_actual: Decimal, meses: int, tasa_anual: Decimal) -> Decimal`
  - `apps.calculos.credito.tasa_efectiva_mensual(tasa_anual: Decimal) -> Decimal`
  - `apps.calculos.credito.FilaAmortizacion(mes: int, mensualidad, intereses, capital, saldo_final, capital_acumulado, pago_anticipado: Decimal)`
  - `apps.calculos.credito.Amortizacion(capital_inicial: Decimal, tasa_mensual: Decimal, filas: tuple[FilaAmortizacion, ...])` con propiedades `mensualidad -> Decimal` (la del mes 1) y `total_intereses -> Decimal`
  - `apps.calculos.credito.amortizar(monto: Decimal, tasa_anual: Decimal, meses: int, comision_apertura: Decimal = CERO, pagos_anticipados: Mapping[int, Decimal] | None = None) -> Amortizacion`

- [ ] **Step 1: Escribir las pruebas que fallan**

`tests/calculos/test_calc_metas.py`:
```python
from decimal import Decimal as D

import pytest

from apps.calculos.comun import redondear
from apps.calculos.metas import aporte_mensual_meta


def test_reproduce_metas_del_excel():
    regalo = aporte_mensual_meta(D("20000"), D("0"), 12, D("0.10"))
    vacaciones = aporte_mensual_meta(D("45000"), D("0"), 12, D("0.10"))

    assert redondear(regalo) == D("1591.65")
    assert redondear(vacaciones) == D("3581.21")
    assert redondear(regalo + vacaciones) == D("5172.87")


def test_tasa_cero_divide_en_partes_iguales():
    assert aporte_mensual_meta(D("1200"), D("0"), 12, D("0")) == D("100")


def test_ahorro_actual_reduce_el_aporte():
    sin_ahorro = aporte_mensual_meta(D("20000"), D("0"), 12, D("0.10"))
    con_ahorro = aporte_mensual_meta(D("20000"), D("5000"), 12, D("0.10"))

    assert con_ahorro < sin_ahorro


def test_meta_ya_alcanzada_requiere_cero():
    assert aporte_mensual_meta(D("1000"), D("2000"), 12, D("0.10")) == D("0")


@pytest.mark.parametrize(
    ("meses", "tasa", "mensaje"),
    [(0, D("0.1"), "meses"), (-3, D("0.1"), "meses"), (12, D("-0.01"), "tasa")],
)
def test_entradas_invalidas(meses, tasa, mensaje):
    with pytest.raises(ValueError, match=mensaje):
        aporte_mensual_meta(D("1000"), D("0"), meses, tasa)
```

`tests/calculos/test_calc_credito.py`:
```python
from decimal import Decimal as D

import pytest

from apps.calculos.comun import CERO, redondear
from apps.calculos.credito import amortizar, tasa_efectiva_mensual


def test_tasa_efectiva_mensual_del_excel():
    r = tasa_efectiva_mensual(D("0.25"))

    assert abs(r - D("0.018769265121506")) < D("1e-14")


def test_reproduce_simulador_del_excel():
    a = amortizar(D("30000"), D("0.25"), 12, comision_apertura=D("0.015"))

    assert a.capital_inicial == D("30450")
    assert redondear(a.mensualidad) == D("2857.62")
    assert redondear(a.total_intereses) == D("3841.45")
    assert len(a.filas) == 12
    assert a.filas[-1].saldo_final == CERO
    assert redondear(a.filas[-1].capital_acumulado) == D("30450.00")


def test_tasa_cero_sin_intereses():
    a = amortizar(D("1200"), D("0"), 12)

    assert a.mensualidad == D("100")
    assert a.total_intereses == CERO
    assert a.filas[-1].saldo_final == CERO


def test_pago_anticipado_reduce_intereses_y_mensualidades():
    base = amortizar(D("30000"), D("0.25"), 12, comision_apertura=D("0.015"))
    con_abono = amortizar(
        D("30000"), D("0.25"), 12, comision_apertura=D("0.015"), pagos_anticipados={3: D("5000")}
    )

    assert con_abono.filas[2].pago_anticipado == D("5000")
    assert con_abono.total_intereses < base.total_intereses
    assert con_abono.filas[3].mensualidad < con_abono.filas[1].mensualidad
    assert con_abono.filas[-1].saldo_final == CERO


def test_pago_anticipado_mayor_al_saldo_liquida_sin_saldo_negativo():
    a = amortizar(D("10000"), D("0.25"), 12, pagos_anticipados={2: D("100000")})

    assert len(a.filas) == 2
    assert a.filas[1].saldo_final == CERO
    assert a.filas[1].pago_anticipado < D("100000")
    assert all(f.saldo_final >= 0 for f in a.filas)


@pytest.mark.parametrize(
    ("kwargs", "mensaje"),
    [
        ({"monto": D("0")}, "monto"),
        ({"meses": 0}, "meses"),
        ({"tasa_anual": D("-0.1")}, "tasa"),
        ({"comision_apertura": D("-0.01")}, "comisión"),
        ({"pagos_anticipados": {13: D("100")}}, "mes"),
        ({"pagos_anticipados": {2: D("-1")}}, "anticipado"),
    ],
)
def test_entradas_invalidas(kwargs, mensaje):
    params = {"monto": D("1000"), "tasa_anual": D("0.1"), "meses": 12} | kwargs
    with pytest.raises(ValueError, match=mensaje):
        amortizar(**params)
```

- [ ] **Step 2: Correr las pruebas para verificar que fallan**

Run: `docker compose run --rm web pytest tests/calculos/test_calc_metas.py tests/calculos/test_calc_credito.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'apps.calculos.metas'`.

- [ ] **Step 3: Implementar**

`apps/calculos/metas.py`:
```python
"""Regla RN-05 del DEF: ahorro mensual necesario para una meta con interés compuesto."""

from decimal import Decimal

from apps.calculos.comun import CERO


def aporte_mensual_meta(
    monto_objetivo: Decimal, ahorro_actual: Decimal, meses: int, tasa_anual: Decimal
) -> Decimal:
    """Aporte = max(0, (M − A·(1+i)^n)·i / ((1+i)^n − 1)), con i = tasa/12."""
    if meses <= 0:
        raise ValueError("Los meses deben ser mayores a cero")
    if tasa_anual < 0:
        raise ValueError("La tasa no puede ser negativa")
    i = tasa_anual / 12
    if i == 0:
        aporte = (monto_objetivo - ahorro_actual) / meses
    else:
        factor = (1 + i) ** meses
        aporte = (monto_objetivo - ahorro_actual * factor) * i / (factor - 1)
    return max(CERO, aporte)
```

`apps/calculos/credito.py`:
```python
"""Regla RN-07 del DEF: tabla de amortización con comisión y pagos anticipados."""

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal

from apps.calculos.comun import CERO

# Residuo por debajo del cual el saldo se considera liquidado (precisión de Decimal).
UMBRAL_LIQUIDADO = Decimal("0.005")


@dataclass(frozen=True)
class FilaAmortizacion:
    mes: int
    mensualidad: Decimal
    intereses: Decimal
    capital: Decimal
    saldo_final: Decimal
    capital_acumulado: Decimal
    pago_anticipado: Decimal


@dataclass(frozen=True)
class Amortizacion:
    capital_inicial: Decimal
    tasa_mensual: Decimal
    filas: tuple[FilaAmortizacion, ...]

    @property
    def mensualidad(self) -> Decimal:
        return self.filas[0].mensualidad if self.filas else CERO

    @property
    def total_intereses(self) -> Decimal:
        return sum((f.intereses for f in self.filas), CERO)


def tasa_efectiva_mensual(tasa_anual: Decimal) -> Decimal:
    """(1 + tasa anual)^(1/12) − 1, igual que el simulador del Excel."""
    return (1 + tasa_anual) ** (Decimal(1) / Decimal(12)) - 1


def _pago_nivelado(tasa: Decimal, periodos: int, saldo: Decimal) -> Decimal:
    """Equivalente a PMT(tasa, periodos, -saldo) de Excel."""
    if tasa == 0:
        return saldo / periodos
    return saldo * tasa / (1 - (1 + tasa) ** -periodos)


def amortizar(
    monto: Decimal,
    tasa_anual: Decimal,
    meses: int,
    comision_apertura: Decimal = CERO,
    pagos_anticipados: Mapping[int, Decimal] | None = None,
) -> Amortizacion:
    pagos_anticipados = dict(pagos_anticipados or {})
    if monto <= 0:
        raise ValueError("El monto debe ser mayor a cero")
    if meses <= 0:
        raise ValueError("Los meses deben ser mayores a cero")
    if tasa_anual < 0:
        raise ValueError("La tasa no puede ser negativa")
    if comision_apertura < 0:
        raise ValueError("La comisión no puede ser negativa")
    for mes, abono in pagos_anticipados.items():
        if not 1 <= mes <= meses:
            raise ValueError(f"El mes {mes} del pago anticipado está fuera del plazo")
        if abono < 0:
            raise ValueError("Un pago anticipado no puede ser negativo")

    tasa = tasa_efectiva_mensual(tasa_anual)
    capital_inicial = monto * (1 + comision_apertura)
    saldo = capital_inicial
    acumulado = CERO
    filas = []
    for mes in range(1, meses + 1):
        if saldo <= 0:
            break
        pago = _pago_nivelado(tasa, meses - mes + 1, saldo)
        intereses = saldo * tasa
        capital_regular = pago - intereses
        anticipado = min(pagos_anticipados.get(mes, CERO), saldo - capital_regular)
        capital = capital_regular + anticipado
        saldo -= capital
        if abs(saldo) < UMBRAL_LIQUIDADO:
            saldo = CERO
        acumulado += capital
        filas.append(
            FilaAmortizacion(
                mes=mes,
                mensualidad=pago + anticipado,
                intereses=intereses,
                capital=capital,
                saldo_final=saldo,
                capital_acumulado=acumulado,
                pago_anticipado=anticipado,
            )
        )
    return Amortizacion(capital_inicial=capital_inicial, tasa_mensual=tasa, filas=tuple(filas))
```

- [ ] **Step 4: Correr las pruebas para verificar que pasan**

Run: `docker compose run --rm web pytest tests/calculos -v`
Expected: todas pasan (`9 + 7 + 11 = 27 passed`).

- [ ] **Step 5: Lint y commit**

```powershell
docker compose run --rm web ruff format apps tests
docker compose run --rm web ruff check .
git add apps/calculos/metas.py apps/calculos/credito.py tests/calculos/test_calc_metas.py tests/calculos/test_calc_credito.py
git commit -m "feat(calculos): metas de ahorro RN-05 y amortizacion RN-07 verificadas contra el Excel" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: Cálculos de deudas y patrimonio (RN-06, RN-08, RN-10)

**Files:**
- Create: `apps/calculos/deudas.py`
- Test: `tests/calculos/test_calc_deudas.py`

**Interfaces:**
- Consumes: `apps.calculos.comun.CERO` (Task 3).
- Produces (`apps.calculos.deudas`):
  - `porcentaje_completado(deuda_inicial: Decimal, deuda_actual: Decimal) -> Decimal | None`
  - `TarjetaCredito(saldo: Decimal, linea: Decimal)` (dataclass)
  - `uso_de_credito(tarjetas: Iterable[TarjetaCredito]) -> Decimal | None`
  - constantes `NIVEL_BUENO = "bueno"`, `NIVEL_CUIDADO = "cuidado"`, `NIVEL_RIESGO = "riesgo"`; `nivel_de_uso(uso: Decimal) -> str`
  - `patrimonio_neto(activos: Iterable[Decimal], saldos_prestamos: Iterable[Decimal], saldos_tarjetas: Iterable[Decimal]) -> Decimal`

- [ ] **Step 1: Escribir las pruebas que fallan**

`tests/calculos/test_calc_deudas.py`:
```python
from decimal import Decimal as D

import pytest

from apps.calculos.comun import redondear
from apps.calculos.deudas import (
    NIVEL_BUENO,
    NIVEL_CUIDADO,
    NIVEL_RIESGO,
    TarjetaCredito,
    nivel_de_uso,
    patrimonio_neto,
    porcentaje_completado,
    uso_de_credito,
)

TARJETAS_EXCEL = [
    TarjetaCredito(saldo=D("2000"), linea=D("2000")),
    TarjetaCredito(saldo=D("681.99"), linea=D("900")),
    TarjetaCredito(saldo=D("1157.02"), linea=D("1200")),
    TarjetaCredito(saldo=D("3000"), linea=D("3000")),
]


def test_porcentaje_completado_del_excel():
    assert redondear(porcentaje_completado(D("41130"), D("38679.72")) * 100) == D("5.96")


def test_porcentaje_completado_sin_deuda_inicial_es_none():
    assert porcentaje_completado(D("0"), D("0")) is None


def test_uso_de_credito_por_saldo_rn08():
    uso = uso_de_credito(TARJETAS_EXCEL)

    assert redondear(uso * 100) == D("96.32")
    assert nivel_de_uso(uso) == NIVEL_RIESGO


@pytest.mark.parametrize(
    ("uso", "nivel"),
    [
        (D("0"), NIVEL_BUENO),
        (D("0.2999"), NIVEL_BUENO),
        (D("0.30"), NIVEL_CUIDADO),
        (D("0.50"), NIVEL_CUIDADO),
        (D("0.5001"), NIVEL_RIESGO),
    ],
)
def test_umbrales_de_nivel(uso, nivel):
    assert nivel_de_uso(uso) == nivel


def test_sin_linea_de_credito_el_uso_es_none():
    assert uso_de_credito([]) is None
    assert uso_de_credito([TarjetaCredito(saldo=D("100"), linea=D("0"))]) is None


def test_saldo_a_favor_cuenta_como_cero():
    uso = uso_de_credito([TarjetaCredito(saldo=D("-500"), linea=D("1000"))])

    assert uso == D("0")


def test_patrimonio_neto_del_excel():
    neto = patrimonio_neto(
        activos=[D("2300000"), D("180000"), D("113519.94")],
        saldos_prestamos=[D("38679.72")],
        saldos_tarjetas=[t.saldo for t in TARJETAS_EXCEL],
    )

    assert neto == D("2548001.21")


def test_patrimonio_ignora_saldos_a_favor_de_tarjetas():
    neto = patrimonio_neto(activos=[D("1000")], saldos_prestamos=[], saldos_tarjetas=[D("-200")])

    assert neto == D("1000")
```

- [ ] **Step 2: Correr las pruebas para verificar que fallan**

Run: `docker compose run --rm web pytest tests/calculos/test_calc_deudas.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'apps.calculos.deudas'`.

- [ ] **Step 3: Implementar**

`apps/calculos/deudas.py`:
```python
"""Reglas RN-06, RN-08 y RN-10 del DEF: avance de créditos, uso de tarjetas y patrimonio."""

from collections.abc import Iterable
from dataclasses import dataclass
from decimal import Decimal

from apps.calculos.comun import CERO

NIVEL_BUENO = "bueno"
NIVEL_CUIDADO = "cuidado"
NIVEL_RIESGO = "riesgo"
LIMITE_BUENO = Decimal("0.30")
LIMITE_CUIDADO = Decimal("0.50")


@dataclass(frozen=True)
class TarjetaCredito:
    saldo: Decimal
    linea: Decimal


def _deuda(saldo: Decimal) -> Decimal:
    """Un saldo a favor (negativo) no es deuda."""
    return max(CERO, saldo)


def porcentaje_completado(deuda_inicial: Decimal, deuda_actual: Decimal) -> Decimal | None:
    """RN-06: 1 − actual / inicial; None si no hay deuda inicial."""
    if deuda_inicial <= 0:
        return None
    return 1 - deuda_actual / deuda_inicial


def uso_de_credito(tarjetas: Iterable[TarjetaCredito]) -> Decimal | None:
    """RN-08: Σ saldo / Σ línea de crédito; None si no hay línea."""
    tarjetas = list(tarjetas)
    linea_total = sum((t.linea for t in tarjetas), CERO)
    if linea_total <= 0:
        return None
    return sum((_deuda(t.saldo) for t in tarjetas), CERO) / linea_total


def nivel_de_uso(uso: Decimal) -> str:
    """< 30% bueno; 30–50% cuidado; > 50% riesgo."""
    if uso < LIMITE_BUENO:
        return NIVEL_BUENO
    if uso <= LIMITE_CUIDADO:
        return NIVEL_CUIDADO
    return NIVEL_RIESGO


def patrimonio_neto(
    activos: Iterable[Decimal],
    saldos_prestamos: Iterable[Decimal],
    saldos_tarjetas: Iterable[Decimal],
) -> Decimal:
    """RN-10: Σ activos − Σ préstamos − Σ tarjetas."""
    deudas = sum((_deuda(s) for s in [*saldos_prestamos, *saldos_tarjetas]), CERO)
    return sum(activos, CERO) - deudas
```

- [ ] **Step 4: Correr las pruebas para verificar que pasan**

Run: `docker compose run --rm web pytest tests/calculos -v`
Expected: `39 passed` (27 previas + 12 nuevas).

- [ ] **Step 5: Lint y commit**

```powershell
docker compose run --rm web ruff format apps tests
docker compose run --rm web ruff check .
git add apps/calculos/deudas.py tests/calculos/test_calc_deudas.py
git commit -m "feat(calculos): avance de creditos, uso de tarjetas por saldo y patrimonio neto" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: Usuario por email, Hogar y Membresía (app `core`)

> ⚠️ El modelo de usuario personalizado debe existir **antes** de la primera migración. Este task reinicia la BD de desarrollo (aún no tiene datos).

**Files:**
- Create: `apps/core/__init__.py` (vacío), `apps/core/apps.py`, `apps/core/models.py`, `apps/core/admin.py`, `apps/core/migrations/__init__.py` (vacío), `apps/core/migrations/0001_initial.py` (generado)
- Modify: `finanzas/settings.py` (INSTALLED_APPS, AUTH_USER_MODEL), `docker/entrypoint.sh` (migrate)
- Test: `tests/core/test_core_usuario.py`

**Interfaces:**
- Produces (`apps.core.models`):
  - `ConMarcasDeTiempo` (abstracto): `creado_en`, `actualizado_en`.
  - `Usuario` (`AUTH_USER_MODEL = "core.Usuario"`): `email` (único sin distinguir mayúsculas, se guarda en minúsculas), `nombre`, `is_active`, `is_staff`, `date_joined`; `Usuario.objects.create_user(email, password=None, **extra)`, `create_superuser(email, password=None, **extra)`, `get_by_natural_key(email)` (case-insensitive).
  - `Hogar(nombre: str, moneda: str = "MXN", zona_horaria: str = "America/Monterrey")`.
  - `Membresia(hogar, usuario, rol)` con `Membresia.Rol.ADMIN|EDITOR|LECTOR`; único por (hogar, usuario). `related_name="membresias"` en ambos FK.

- [ ] **Step 1: Escribir las pruebas que fallan**

`tests/core/test_core_usuario.py`:
```python
import pytest
from django.contrib.auth import authenticate, get_user_model
from django.db import IntegrityError

from apps.core.models import Hogar, Membresia

pytestmark = pytest.mark.django_db


def test_modelo_de_usuario_es_el_personalizado():
    assert get_user_model()._meta.label == "core.Usuario"


def test_crear_usuario_normaliza_email_a_minusculas():
    usuario = get_user_model().objects.create_user(
        email="  Julio@Example.COM ", password="clave-segura-123"
    )

    assert usuario.email == "julio@example.com"
    assert usuario.check_password("clave-segura-123")
    assert not usuario.is_staff


def test_email_sin_distinguir_mayusculas_es_unico():
    Usuario = get_user_model()
    Usuario.objects.create_user(email="julio@example.com", password="x-clave-123")

    with pytest.raises(IntegrityError):
        Usuario.objects.create_user(email="JULIO@example.com", password="x-clave-123")


def test_login_ignora_mayusculas_del_email():
    get_user_model().objects.create_user(email="julio@example.com", password="clave-segura-123")

    assert authenticate(username="Julio@Example.com", password="clave-segura-123") is not None


def test_email_obligatorio():
    with pytest.raises(ValueError, match="email"):
        get_user_model().objects.create_user(email="", password="x")


def test_superusuario():
    admin = get_user_model().objects.create_superuser(email="a@example.com", password="clave-123-x")

    assert admin.is_staff and admin.is_superuser


def test_membresia_unica_por_hogar_y_usuario():
    usuario = get_user_model().objects.create_user(email="j@example.com", password="clave-123-x")
    hogar = Hogar.objects.create(nombre="Familia")
    Membresia.objects.create(hogar=hogar, usuario=usuario)

    assert hogar.moneda == "MXN"
    assert hogar.zona_horaria == "America/Monterrey"
    with pytest.raises(IntegrityError):
        Membresia.objects.create(hogar=hogar, usuario=usuario)


def test_admin_de_usuarios_carga(client):
    admin = get_user_model().objects.create_superuser(email="a@example.com", password="clave-123-x")
    client.force_login(admin)

    assert client.get("/admin/core/usuario/").status_code == 200
    assert client.get("/admin/core/usuario/add/").status_code == 200
    assert client.get("/admin/core/hogar/").status_code == 200
```

- [ ] **Step 2: Correr las pruebas para verificar que fallan**

Run: `docker compose run --rm web pytest tests/core/test_core_usuario.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'apps.core'`.

- [ ] **Step 3: Implementar la app `core`**

`apps/core/apps.py`:
```python
from django.apps import AppConfig


class CoreConfig(AppConfig):
    name = "apps.core"
    verbose_name = "Núcleo"
```

`apps/core/models.py`:
```python
from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.db import models
from django.db.models.functions import Lower
from django.utils import timezone


class ConMarcasDeTiempo(models.Model):
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class UsuarioManager(BaseUserManager):
    use_in_migrations = True

    def _crear(self, email, password, **extra):
        if not email or not email.strip():
            raise ValueError("El email es obligatorio")
        usuario = self.model(email=email.strip().lower(), **extra)
        usuario.set_password(password)
        usuario.save(using=self._db)
        return usuario

    def create_user(self, email, password=None, **extra):
        extra.setdefault("is_staff", False)
        extra.setdefault("is_superuser", False)
        return self._crear(email, password, **extra)

    def create_superuser(self, email, password=None, **extra):
        extra["is_staff"] = True
        extra["is_superuser"] = True
        return self._crear(email, password, **extra)

    def get_by_natural_key(self, email):
        return self.get(email__iexact=email.strip())


class Usuario(AbstractBaseUser, PermissionsMixin):
    email = models.EmailField("email", unique=True)
    nombre = models.CharField(max_length=120, blank=True)
    is_active = models.BooleanField("activo", default=True)
    is_staff = models.BooleanField("acceso al admin", default=False)
    date_joined = models.DateTimeField("fecha de alta", default=timezone.now)

    objects = UsuarioManager()

    USERNAME_FIELD = "email"
    EMAIL_FIELD = "email"
    REQUIRED_FIELDS = []

    class Meta:
        verbose_name = "usuario"
        verbose_name_plural = "usuarios"
        constraints = [models.UniqueConstraint(Lower("email"), name="usuario_email_unico_ci")]

    def __str__(self):
        return self.email


class Hogar(ConMarcasDeTiempo):
    nombre = models.CharField(max_length=120)
    moneda = models.CharField(max_length=3, default="MXN")
    zona_horaria = models.CharField(max_length=64, default="America/Monterrey")

    class Meta:
        verbose_name = "hogar"
        verbose_name_plural = "hogares"

    def __str__(self):
        return self.nombre


class Membresia(ConMarcasDeTiempo):
    class Rol(models.TextChoices):
        ADMIN = "admin", "Administrador"
        EDITOR = "editor", "Editor"
        LECTOR = "lector", "Lector"

    hogar = models.ForeignKey(Hogar, on_delete=models.CASCADE, related_name="membresias")
    usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name="membresias")
    rol = models.CharField(max_length=10, choices=Rol.choices, default=Rol.ADMIN)

    class Meta:
        verbose_name = "membresía"
        verbose_name_plural = "membresías"
        constraints = [
            models.UniqueConstraint(fields=["hogar", "usuario"], name="membresia_unica")
        ]

    def __str__(self):
        return f"{self.usuario} en {self.hogar} ({self.rol})"
```

`apps/core/admin.py`:
```python
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.forms import UserChangeForm, UserCreationForm

from apps.core.models import Hogar, Membresia, Usuario


class UsuarioCreationForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = Usuario
        fields = ("email",)


class UsuarioChangeForm(UserChangeForm):
    class Meta(UserChangeForm.Meta):
        model = Usuario
        fields = ("email", "nombre")


@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):
    add_form = UsuarioCreationForm
    form = UsuarioChangeForm
    model = Usuario
    ordering = ("email",)
    list_display = ("email", "nombre", "is_staff", "is_active")
    search_fields = ("email", "nombre")
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Datos", {"fields": ("nombre",)}),
        (
            "Permisos",
            {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")},
        ),
        ("Fechas", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = ((None, {"classes": ("wide",), "fields": ("email", "password1", "password2")}),)


class MembresiaInline(admin.TabularInline):
    model = Membresia
    extra = 0


@admin.register(Hogar)
class HogarAdmin(admin.ModelAdmin):
    list_display = ("nombre", "moneda", "zona_horaria", "creado_en")
    inlines = [MembresiaInline]
```

`apps/core/migrations/__init__.py`: vacío.

- [ ] **Step 4: Registrar la app y el usuario en `finanzas/settings.py`**

Añadir `"apps.core",` al final de `INSTALLED_APPS` y, debajo de `DEFAULT_AUTO_FIELD`:
```python
AUTH_USER_MODEL = "core.Usuario"
```

- [ ] **Step 5: Hacer que el contenedor aplique migraciones al iniciar**

`docker/entrypoint.sh`:
```sh
#!/bin/sh
set -e
if [ "${DJANGO_MIGRAR:-1}" = "1" ]; then
    python manage.py migrate --noinput
fi
exec "$@"
```

- [ ] **Step 6: Reiniciar la BD de desarrollo y generar la migración**

Run:
```powershell
docker compose down -v
docker compose run --rm -e DJANGO_MIGRAR=0 web python manage.py makemigrations core
```
Expected: `Migrations for 'core': apps/core/migrations/0001_initial.py` con `Create model Usuario`, `Hogar`, `Membresia`.

- [ ] **Step 7: Correr las pruebas para verificar que pasan**

Run: `docker compose run --rm web pytest -v`
Expected: todas pasan (`39` de cálculos + `1` salud + `8` de usuario = `48 passed`).

- [ ] **Step 8: Lint y commit**

```powershell
docker compose run --rm web ruff format apps tests
docker compose run --rm web ruff check .
git add apps/core finanzas/settings.py docker/entrypoint.sh tests/core/test_core_usuario.py
git commit -m "feat(core): usuario por email, hogar y membresia con admin" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: Hogar activo por petición y servicio `crear_hogar`

**Files:**
- Create: `apps/core/middleware.py`, `apps/core/servicios.py`, `tests/conftest.py`
- Modify: `finanzas/settings.py` (MIDDLEWARE)
- Test: `tests/core/test_core_hogar.py`

**Interfaces:**
- Consumes: `Usuario`, `Hogar`, `Membresia` (Task 6).
- Produces:
  - `apps.core.servicios.crear_hogar(nombre: str, usuario: Usuario, rol: str = Membresia.Rol.ADMIN) -> Hogar` (atómico; crea hogar + membresía).
  - `apps.core.middleware.HogarMiddleware`: asigna `request.hogar: Hogar | None` (primer hogar del usuario por antigüedad de la membresía; `None` si es anónimo o no tiene).
  - Fixtures en `tests/conftest.py`: `usuario` (email `julio@example.com`, contraseña `clave-segura-123`), `hogar` (hogar "Familia Prueba" de `usuario`), `otro_hogar` (hogar "Otra Familia" de otro usuario).

- [ ] **Step 1: Crear fixtures compartidas**

`tests/conftest.py`:
```python
import pytest
from django.contrib.auth import get_user_model

from apps.core.servicios import crear_hogar


@pytest.fixture
def usuario(db):
    return get_user_model().objects.create_user(
        email="julio@example.com", password="clave-segura-123"
    )


@pytest.fixture
def hogar(usuario):
    return crear_hogar("Familia Prueba", usuario)


@pytest.fixture
def otro_hogar(db):
    otro = get_user_model().objects.create_user(email="otro@example.com", password="clave-123-x")
    return crear_hogar("Otra Familia", otro)
```

- [ ] **Step 2: Escribir las pruebas que fallan**

`tests/core/test_core_hogar.py`:
```python
import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.http import HttpResponse

from apps.core.middleware import HogarMiddleware
from apps.core.models import Membresia
from apps.core.servicios import crear_hogar


def _procesar(request):
    HogarMiddleware(lambda r: HttpResponse())(request)
    return request


def test_crear_hogar_crea_membresia_admin(usuario):
    hogar = crear_hogar("Familia Armijo", usuario)

    membresia = Membresia.objects.get(hogar=hogar, usuario=usuario)
    assert membresia.rol == Membresia.Rol.ADMIN
    assert hogar.nombre == "Familia Armijo"


def test_middleware_asigna_el_hogar_del_usuario(rf, usuario, hogar, otro_hogar):
    request = rf.get("/")
    request.user = usuario

    assert _procesar(request).hogar == hogar


def test_middleware_usuario_sin_hogar(rf, db):
    request = rf.get("/")
    request.user = get_user_model().objects.create_user(email="s@example.com", password="x-12345")

    assert _procesar(request).hogar is None


def test_middleware_anonimo(rf):
    request = rf.get("/")
    request.user = AnonymousUser()

    assert _procesar(request).hogar is None


@pytest.mark.django_db
def test_middleware_instalado_en_peticiones_reales(client, usuario, hogar):
    client.force_login(usuario)

    respuesta = client.get("/salud/")

    assert respuesta.wsgi_request.hogar == hogar
```

- [ ] **Step 3: Correr las pruebas para verificar que fallan**

Run: `docker compose run --rm web pytest tests/core/test_core_hogar.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'apps.core.servicios'`.

- [ ] **Step 4: Implementar**

`apps/core/servicios.py`:
```python
from django.db import transaction

from apps.core.models import Hogar, Membresia


@transaction.atomic
def crear_hogar(nombre, usuario, rol=Membresia.Rol.ADMIN):
    """Crea un hogar y da al usuario acceso con el rol indicado."""
    hogar = Hogar.objects.create(nombre=nombre)
    Membresia.objects.create(hogar=hogar, usuario=usuario, rol=rol)
    return hogar
```

`apps/core/middleware.py`:
```python
from apps.core.models import Membresia


class HogarMiddleware:
    """Expone en request.hogar el hogar activo del usuario autenticado (o None)."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.hogar = None
        if request.user.is_authenticated:
            membresia = (
                Membresia.objects.select_related("hogar")
                .filter(usuario=request.user)
                .order_by("creado_en", "id")
                .first()
            )
            if membresia:
                request.hogar = membresia.hogar
        return self.get_response(request)
```

En `finanzas/settings.py`, añadir justo después de `"django.contrib.auth.middleware.AuthenticationMiddleware",`:
```python
    "apps.core.middleware.HogarMiddleware",
```

- [ ] **Step 5: Correr las pruebas para verificar que pasan**

Run: `docker compose run --rm web pytest -v`
Expected: `53 passed`.

- [ ] **Step 6: Lint y commit**

```powershell
docker compose run --rm web ruff format apps tests
docker compose run --rm web ruff check .
git add apps/core/middleware.py apps/core/servicios.py finanzas/settings.py tests/conftest.py tests/core/test_core_hogar.py
git commit -m "feat(core): hogar activo por peticion y servicio crear_hogar" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 8: Base multi-hogar (`ModeloDeHogar`) y modelos de catálogos

**Files:**
- Modify: `apps/core/models.py` (añadir `HogarQuerySet` y `ModeloDeHogar`)
- Create: `apps/catalogos/__init__.py` (vacío), `apps/catalogos/apps.py`, `apps/catalogos/models.py`, `apps/catalogos/admin.py`, `apps/catalogos/migrations/__init__.py` (vacío), `apps/catalogos/migrations/0001_initial.py` (generado)
- Modify: `finanzas/settings.py` (INSTALLED_APPS)
- Test: `tests/catalogos/test_catalogos_modelos.py`

**Interfaces:**
- Consumes: `Hogar`, `ConMarcasDeTiempo` (Task 6); fixtures `hogar`, `otro_hogar` (Task 7).
- Produces:
  - `apps.core.models.HogarQuerySet.del_hogar(hogar) -> QuerySet`; `ModeloDeHogar` (abstracto): FK `hogar`, `objects = HogarQuerySet.as_manager()`, `clean()` que rechaza FKs a objetos de otro hogar con `ValidationError({campo: "Pertenece a otro hogar."})`.
  - `apps.catalogos.models`: `Persona(hogar, nombre, parentesco, activo)`, `Domicilio(hogar, alias, direccion, activo)`, `Categoria(hogar, nombre, icono, orden, activo)`, `Cuenta(hogar, nombre, tipo, institucion, producto, titular→Persona, ultimos_digitos, linea_credito, tasa_anual, paga_total_mensual, dia_corte, dia_pago, monto_inicial, mensualidad, saldo_actual, fecha_saldo, activo)` con `Cuenta.Tipo.EFECTIVO|DEBITO|CREDITO|PRESTAMO|AHORRO|INVERSION`, `Concepto(hogar, categoria, nombre, es_fijo, es_hormiga, persona, domicilio, cuenta, activo)`, `TasaMercado(institucion, producto, tasa_promedio, fecha_referencia)` (global, sin hogar). Campos y tipos según `docs/modelo-datos.dbml`.

- [ ] **Step 1: Escribir las pruebas que fallan**

`tests/catalogos/test_catalogos_modelos.py`:
```python
from decimal import Decimal as D

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError

from apps.catalogos.models import Categoria, Concepto, Cuenta, Domicilio, Persona, TasaMercado

pytestmark = pytest.mark.django_db


def test_del_hogar_aisla_los_datos(hogar, otro_hogar):
    Persona.objects.create(hogar=hogar, nombre="Monze")
    Persona.objects.create(hogar=otro_hogar, nombre="Ajeno")

    nombres = list(Persona.objects.del_hogar(hogar).values_list("nombre", flat=True))

    assert nombres == ["Monze"]


def test_nombre_unico_por_hogar_pero_repetible_entre_hogares(hogar, otro_hogar):
    Persona.objects.create(hogar=hogar, nombre="Fidel")
    Persona.objects.create(hogar=otro_hogar, nombre="Fidel")

    with pytest.raises(IntegrityError):
        Persona.objects.create(hogar=hogar, nombre="Fidel")


def test_concepto_con_categoria_de_otro_hogar_es_invalido(hogar, otro_hogar):
    categoria_ajena = Categoria.objects.create(hogar=otro_hogar, nombre="Casa")
    concepto = Concepto(hogar=hogar, categoria=categoria_ajena, nombre="Luz")

    with pytest.raises(ValidationError) as error:
        concepto.full_clean()

    assert "categoria" in error.value.message_dict


def test_concepto_con_persona_de_otro_hogar_es_invalido(hogar, otro_hogar):
    categoria = Categoria.objects.create(hogar=hogar, nombre="Casa")
    persona_ajena = Persona.objects.create(hogar=otro_hogar, nombre="Ajeno")
    concepto = Concepto(hogar=hogar, categoria=categoria, nombre="Luz", persona=persona_ajena)

    with pytest.raises(ValidationError) as error:
        concepto.full_clean()

    assert "persona" in error.value.message_dict


def test_concepto_valido_por_domicilio(hogar):
    casa = Categoria.objects.create(hogar=hogar, nombre="Casa")
    cedro = Domicilio.objects.create(hogar=hogar, alias="Casa Cedro")
    fidel = Domicilio.objects.create(hogar=hogar, alias="Casa Fidel")

    luz_cedro = Concepto(hogar=hogar, categoria=casa, nombre="Luz", domicilio=cedro)
    luz_cedro.full_clean()
    luz_cedro.save()
    Concepto.objects.create(hogar=hogar, categoria=casa, nombre="Luz", domicilio=fidel)

    assert Concepto.objects.del_hogar(hogar).filter(nombre="Luz").count() == 2


def test_concepto_duplicado_sin_domicilio_es_rechazado(hogar):
    casa = Categoria.objects.create(hogar=hogar, nombre="Casa")
    Concepto.objects.create(hogar=hogar, categoria=casa, nombre="Gas")

    with pytest.raises(IntegrityError):
        Concepto.objects.create(hogar=hogar, categoria=casa, nombre="Gas")


def test_cuenta_de_credito_con_campos_de_tarjeta(hogar):
    titular = Persona.objects.create(hogar=hogar, nombre="Julio")
    cuenta = Cuenta.objects.create(
        hogar=hogar,
        nombre="Stori",
        tipo=Cuenta.Tipo.CREDITO,
        institucion="Stori",
        producto="Stori Clásica",
        titular=titular,
        linea_credito=D("900"),
        saldo_actual=D("681.99"),
        dia_corte=13,
        dia_pago=3,
    )

    cuenta.full_clean()
    assert cuenta.saldo_actual == D("681.99")


def test_dia_de_corte_fuera_de_rango_es_invalido(hogar):
    cuenta = Cuenta(hogar=hogar, nombre="Hey", tipo=Cuenta.Tipo.CREDITO, dia_corte=32)

    with pytest.raises(ValidationError) as error:
        cuenta.full_clean()

    assert "dia_corte" in error.value.message_dict


def test_tasa_de_mercado_es_global():
    tasa = TasaMercado.objects.create(
        institucion="Stori", producto="Stori Clásica", tasa_promedio=D("1.0930")
    )

    assert not hasattr(tasa, "hogar")


def test_admin_de_catalogos_carga(client, usuario):
    usuario.is_staff = True
    usuario.is_superuser = True
    usuario.save()
    client.force_login(usuario)

    for modelo in ["persona", "domicilio", "categoria", "concepto", "cuenta", "tasamercado"]:
        assert client.get(f"/admin/catalogos/{modelo}/").status_code == 200, modelo
```

- [ ] **Step 2: Correr las pruebas para verificar que fallan**

Run: `docker compose run --rm web pytest tests/catalogos/test_catalogos_modelos.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'apps.catalogos'`.

- [ ] **Step 3: Añadir la base multi-hogar al final de `apps/core/models.py`**

Añadir `from django.core.exceptions import ValidationError` a los imports, y al final del archivo:
```python
class HogarQuerySet(models.QuerySet):
    def del_hogar(self, hogar):
        return self.filter(hogar=hogar)


class ModeloDeHogar(ConMarcasDeTiempo):
    """Base de todo dato de negocio: pertenece a un hogar y no puede apuntar a otro."""

    hogar = models.ForeignKey(Hogar, on_delete=models.CASCADE, related_name="+")

    objects = HogarQuerySet.as_manager()

    class Meta:
        abstract = True

    def clean(self):
        super().clean()
        if self.hogar_id is None:
            return
        errores = {}
        for campo in self._meta.concrete_fields:
            if not campo.many_to_one or campo.name == "hogar":
                continue
            relacionado = getattr(self, campo.name, None)
            if isinstance(relacionado, ModeloDeHogar) and relacionado.hogar_id != self.hogar_id:
                errores[campo.name] = "Pertenece a otro hogar."
        if errores:
            raise ValidationError(errores)
```

- [ ] **Step 4: Crear la app `catalogos`**

`apps/catalogos/apps.py`:
```python
from django.apps import AppConfig


class CatalogosConfig(AppConfig):
    name = "apps.catalogos"
    verbose_name = "Catálogos"
```

`apps/catalogos/models.py`:
```python
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from apps.core.models import ConMarcasDeTiempo, ModeloDeHogar

DINERO = {"max_digits": 12, "decimal_places": 2}
TASA = {"max_digits": 7, "decimal_places": 4}
DIA_DEL_MES = [MinValueValidator(1), MaxValueValidator(31)]


class Persona(ModeloDeHogar):
    nombre = models.CharField(max_length=80)
    parentesco = models.CharField(max_length=40, blank=True)
    activo = models.BooleanField(default=True)

    class Meta:
        ordering = ["nombre"]
        constraints = [
            models.UniqueConstraint(fields=["hogar", "nombre"], name="persona_nombre_unico")
        ]

    def __str__(self):
        return self.nombre


class Domicilio(ModeloDeHogar):
    alias = models.CharField(max_length=80)
    direccion = models.CharField(max_length=255, blank=True)
    activo = models.BooleanField(default=True)

    class Meta:
        ordering = ["alias"]
        constraints = [
            models.UniqueConstraint(fields=["hogar", "alias"], name="domicilio_alias_unico")
        ]

    def __str__(self):
        return self.alias


class Categoria(ModeloDeHogar):
    nombre = models.CharField(max_length=60)
    icono = models.CharField(max_length=8, blank=True)
    orden = models.PositiveSmallIntegerField(default=0)
    activo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "categoría"
        ordering = ["orden", "nombre"]
        constraints = [
            models.UniqueConstraint(fields=["hogar", "nombre"], name="categoria_nombre_unico")
        ]

    def __str__(self):
        return f"{self.icono} {self.nombre}".strip()


class Cuenta(ModeloDeHogar):
    class Tipo(models.TextChoices):
        EFECTIVO = "efectivo", "Efectivo"
        DEBITO = "debito", "Débito"
        CREDITO = "credito", "Tarjeta de crédito"
        PRESTAMO = "prestamo", "Préstamo / crédito"
        AHORRO = "ahorro", "Ahorro"
        INVERSION = "inversion", "Inversión"

    nombre = models.CharField(max_length=80)
    tipo = models.CharField(max_length=10, choices=Tipo.choices)
    institucion = models.CharField(max_length=80, blank=True)
    producto = models.CharField(max_length=80, blank=True)
    titular = models.ForeignKey(
        Persona, null=True, blank=True, on_delete=models.SET_NULL, related_name="cuentas"
    )
    ultimos_digitos = models.CharField(max_length=4, blank=True)
    linea_credito = models.DecimalField(null=True, blank=True, **DINERO)
    tasa_anual = models.DecimalField(null=True, blank=True, **TASA)
    paga_total_mensual = models.BooleanField(null=True, blank=True)
    dia_corte = models.PositiveSmallIntegerField(null=True, blank=True, validators=DIA_DEL_MES)
    dia_pago = models.PositiveSmallIntegerField(null=True, blank=True, validators=DIA_DEL_MES)
    monto_inicial = models.DecimalField(null=True, blank=True, **DINERO)
    mensualidad = models.DecimalField(null=True, blank=True, **DINERO)
    saldo_actual = models.DecimalField(default=0, **DINERO)
    fecha_saldo = models.DateField(null=True, blank=True)
    activo = models.BooleanField(default=True)

    class Meta:
        ordering = ["nombre"]
        constraints = [
            models.UniqueConstraint(fields=["hogar", "nombre"], name="cuenta_nombre_unico")
        ]

    def __str__(self):
        return self.nombre


class Concepto(ModeloDeHogar):
    categoria = models.ForeignKey(Categoria, on_delete=models.PROTECT, related_name="conceptos")
    nombre = models.CharField(max_length=80)
    es_fijo = models.BooleanField(default=False)
    es_hormiga = models.BooleanField(default=False)
    persona = models.ForeignKey(Persona, null=True, blank=True, on_delete=models.SET_NULL)
    domicilio = models.ForeignKey(Domicilio, null=True, blank=True, on_delete=models.SET_NULL)
    cuenta = models.ForeignKey(Cuenta, null=True, blank=True, on_delete=models.SET_NULL)
    activo = models.BooleanField(default=True)

    class Meta:
        ordering = ["categoria__orden", "nombre"]
        constraints = [
            models.UniqueConstraint(
                fields=["categoria", "nombre", "domicilio"],
                name="concepto_unico_por_domicilio",
                nulls_distinct=False,
            )
        ]

    def __str__(self):
        return f"{self.nombre} ({self.domicilio})" if self.domicilio_id else self.nombre


class TasaMercado(ConMarcasDeTiempo):
    """Catálogo global de tasas promedio por tarjeta (de la hoja oculta del Excel)."""

    institucion = models.CharField(max_length=80)
    producto = models.CharField(max_length=80)
    tasa_promedio = models.DecimalField(**TASA)
    fecha_referencia = models.DateField(null=True, blank=True)

    class Meta:
        verbose_name = "tasa de mercado"
        verbose_name_plural = "tasas de mercado"
        ordering = ["institucion", "producto"]
        constraints = [
            models.UniqueConstraint(
                fields=["institucion", "producto"], name="tasa_mercado_unica"
            )
        ]

    def __str__(self):
        return f"{self.institucion} — {self.producto}"
```

`apps/catalogos/admin.py`:
```python
from django.contrib import admin

from apps.catalogos.models import Categoria, Concepto, Cuenta, Domicilio, Persona, TasaMercado


@admin.register(Persona)
class PersonaAdmin(admin.ModelAdmin):
    list_display = ("nombre", "parentesco", "activo", "hogar")
    list_filter = ("hogar", "activo")


@admin.register(Domicilio)
class DomicilioAdmin(admin.ModelAdmin):
    list_display = ("alias", "direccion", "activo", "hogar")
    list_filter = ("hogar", "activo")


@admin.register(Categoria)
class CategoriaAdmin(admin.ModelAdmin):
    list_display = ("nombre", "icono", "orden", "activo", "hogar")
    list_filter = ("hogar", "activo")


@admin.register(Concepto)
class ConceptoAdmin(admin.ModelAdmin):
    list_display = ("nombre", "categoria", "domicilio", "persona", "es_fijo", "es_hormiga")
    list_filter = ("hogar", "categoria", "domicilio", "es_fijo", "es_hormiga")
    search_fields = ("nombre",)


@admin.register(Cuenta)
class CuentaAdmin(admin.ModelAdmin):
    list_display = ("nombre", "tipo", "institucion", "saldo_actual", "linea_credito", "activo")
    list_filter = ("hogar", "tipo", "activo")


@admin.register(TasaMercado)
class TasaMercadoAdmin(admin.ModelAdmin):
    list_display = ("institucion", "producto", "tasa_promedio", "fecha_referencia")
    search_fields = ("institucion", "producto")
```

En `finanzas/settings.py`, añadir `"apps.catalogos",` después de `"apps.core",` en `INSTALLED_APPS`.

- [ ] **Step 5: Generar la migración**

Run: `docker compose run --rm -e DJANGO_MIGRAR=0 web python manage.py makemigrations catalogos`
Expected: `apps/catalogos/migrations/0001_initial.py` con `Create model Persona, Domicilio, Categoria, Cuenta, Concepto, TasaMercado`. (Core no debe generar migración nueva: `ModeloDeHogar` es abstracto. Confirmar con `docker compose run --rm -e DJANGO_MIGRAR=0 web python manage.py makemigrations --check --dry-run` → `No changes detected`.)

- [ ] **Step 6: Correr las pruebas para verificar que pasan**

Run: `docker compose run --rm web pytest -v`
Expected: `63 passed`.

- [ ] **Step 7: Lint y commit**

```powershell
docker compose run --rm web ruff format apps tests
docker compose run --rm web ruff check .
git add apps/core/models.py apps/catalogos finanzas/settings.py tests/catalogos/test_catalogos_modelos.py
git commit -m "feat(catalogos): personas, domicilios, categorias, conceptos, cuentas y tasas con aislamiento por hogar" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 9: Siembra de categorías, comando `crear_hogar` y verificación de punta a punta

**Files:**
- Create: `apps/catalogos/servicios.py`, `apps/catalogos/management/__init__.py` (vacío), `apps/catalogos/management/commands/__init__.py` (vacío), `apps/catalogos/management/commands/crear_hogar.py`
- Modify: `README.md` (sección "Primer uso"), `..\CLAUDE.md` (estado; está fuera del repo, no se commitea)
- Test: `tests/catalogos/test_catalogos_siembra.py`

**Interfaces:**
- Consumes: `crear_hogar` (Task 7), `Categoria` (Task 8).
- Produces:
  - `apps.catalogos.servicios.CATEGORIAS_INICIALES: list[tuple[str, str]]` (nombre, icono) — las 12 del Excel en orden.
  - `apps.catalogos.servicios.sembrar_catalogos(hogar) -> int` (idempotente; devuelve cuántas categorías creó).
  - Comando `python manage.py crear_hogar --nombre "<nombre>" --email <email>`: crea el hogar para un usuario existente y siembra catálogos; `CommandError` si el usuario no existe o ya pertenece a un hogar.

- [ ] **Step 1: Escribir las pruebas que fallan**

`tests/catalogos/test_catalogos_siembra.py`:
```python
import pytest
from django.core.management import CommandError, call_command

from apps.catalogos.models import Categoria
from apps.catalogos.servicios import CATEGORIAS_INICIALES, sembrar_catalogos
from apps.core.models import Membresia

pytestmark = pytest.mark.django_db

NOMBRES_EXCEL = [
    "Casa", "Comida", "Familia", "Transporte", "Viajes", "Deudas", "Salud",
    "Suscripciones", "Gastos anuales", "Cuidado personal", "Entretenimiento", "Otros",
]


def test_siembra_las_12_categorias_del_excel_en_orden(hogar):
    creadas = sembrar_catalogos(hogar)

    assert creadas == 12
    assert [n for n, _ in CATEGORIAS_INICIALES] == NOMBRES_EXCEL
    nombres = list(Categoria.objects.del_hogar(hogar).values_list("nombre", flat=True))
    assert nombres == NOMBRES_EXCEL


def test_siembra_es_idempotente(hogar):
    sembrar_catalogos(hogar)

    assert sembrar_catalogos(hogar) == 0
    assert Categoria.objects.del_hogar(hogar).count() == 12


def test_comando_crea_hogar_y_siembra(usuario):
    call_command("crear_hogar", nombre="Familia Armijo", email="JULIO@example.com")

    membresia = Membresia.objects.get(usuario=usuario)
    assert membresia.hogar.nombre == "Familia Armijo"
    assert Categoria.objects.del_hogar(membresia.hogar).count() == 12


def test_comando_falla_si_el_usuario_no_existe(db):
    with pytest.raises(CommandError, match="No existe"):
        call_command("crear_hogar", nombre="X", email="nadie@example.com")


def test_comando_falla_si_el_usuario_ya_tiene_hogar(usuario, hogar):
    with pytest.raises(CommandError, match="ya pertenece"):
        call_command("crear_hogar", nombre="Otro", email="julio@example.com")
```

- [ ] **Step 2: Correr las pruebas para verificar que fallan**

Run: `docker compose run --rm web pytest tests/catalogos/test_catalogos_siembra.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'apps.catalogos.servicios'`.

- [ ] **Step 3: Implementar**

`apps/catalogos/servicios.py`:
```python
from apps.catalogos.models import Categoria

# Las 12 categorías del Excel "Financial Planner template", en su orden original.
CATEGORIAS_INICIALES = [
    ("Casa", "🏡"),
    ("Comida", "🥑"),
    ("Familia", "❤️"),
    ("Transporte", "🚓"),
    ("Viajes", "✈️"),
    ("Deudas", "🏦"),
    ("Salud", "🚑"),
    ("Suscripciones", "📺"),
    ("Gastos anuales", "🗓️"),
    ("Cuidado personal", "💅"),
    ("Entretenimiento", "📽️"),
    ("Otros", "🛸"),
]


def sembrar_catalogos(hogar):
    """Crea las categorías iniciales que falten. Devuelve cuántas creó."""
    creadas = 0
    for orden, (nombre, icono) in enumerate(CATEGORIAS_INICIALES, start=1):
        _, nueva = Categoria.objects.get_or_create(
            hogar=hogar, nombre=nombre, defaults={"icono": icono, "orden": orden}
        )
        creadas += nueva
    return creadas
```

`apps/catalogos/management/commands/crear_hogar.py`:
```python
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.catalogos.servicios import sembrar_catalogos
from apps.core.models import Membresia
from apps.core.servicios import crear_hogar


class Command(BaseCommand):
    help = "Crea un hogar para un usuario existente y siembra los catálogos iniciales."

    def add_arguments(self, parser):
        parser.add_argument("--nombre", required=True, help="Nombre del hogar")
        parser.add_argument("--email", required=True, help="Email del usuario administrador")

    @transaction.atomic
    def handle(self, *args, nombre, email, **options):
        Usuario = get_user_model()
        try:
            usuario = Usuario.objects.get_by_natural_key(email)
        except Usuario.DoesNotExist as error:
            raise CommandError(f"No existe un usuario con email {email}") from error
        if Membresia.objects.filter(usuario=usuario).exists():
            raise CommandError(f"{usuario.email} ya pertenece a un hogar")

        hogar = crear_hogar(nombre, usuario)
        categorias = sembrar_catalogos(hogar)
        self.stdout.write(
            self.style.SUCCESS(f"Hogar '{hogar}' creado con {categorias} categorías.")
        )
```

- [ ] **Step 4: Correr toda la suite**

Run: `docker compose run --rm web pytest --cov=apps --cov-report=term-missing`
Expected: `68 passed`; cobertura de `apps/calculos` = 100%.

- [ ] **Step 5: Verificación manual de punta a punta (con tus datos reales, solo local)**

Run:
```powershell
docker compose build
docker compose up -d
docker compose exec web python manage.py createsuperuser --email tu-email@ejemplo.com
docker compose exec web python manage.py crear_hogar --nombre "Familia Armijo" --email tu-email@ejemplo.com
```
Expected: `Hogar 'Familia Armijo' creado con 12 categorías.`
Abrir `http://localhost:8000/admin/`, iniciar sesión, y comprobar:
1. *Catálogos → Categorías* muestra las 12 en orden con icono.
2. Se puede crear una *Persona* "Monze", un *Domicilio* "Casa Fidel" y un *Concepto* "Luz" en Casa con domicilio Casa Fidel.
3. `http://localhost:8000/salud/` responde `{"estado": "ok"}`.

- [ ] **Step 6: Documentar el primer uso en `README.md`**

Añadir al final de `README.md`:
~~~markdown
## Primer uso

```powershell
docker compose up -d
docker compose exec web python manage.py createsuperuser --email tu@email.com
docker compose exec web python manage.py crear_hogar --nombre "Mi Familia" --email tu@email.com
```

Luego entra a http://localhost:8000/admin/ (en el plan 2 se agrega la interfaz principal).
~~~

- [ ] **Step 7: Actualizar el estado en `..\CLAUDE.md` (memoria, fuera del repo)**

Reemplazar la sección `## Estado / siguiente paso` por:
```markdown
## Estado / siguiente paso
- Plan 1 (Fundación) completado: Docker + Django + CI, usuario/hogar, catálogos en admin, `apps/calculos` (RN-01..08, RN-10) verificado contra el Excel.
- Siguiente: escribir y ejecutar el plan 2 (operación diaria: UI, movimientos, presupuesto, tablero).
```

- [ ] **Step 8: Lint y commit**

```powershell
docker compose run --rm web ruff format apps tests
docker compose run --rm web ruff check .
git add apps/catalogos README.md tests/catalogos/test_catalogos_siembra.py
git commit -m "feat(catalogos): siembra de categorias y comando crear_hogar" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```
