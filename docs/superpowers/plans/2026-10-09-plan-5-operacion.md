# Plan 5 — Operación: PWA, Tailscale, respaldos e importación del Excel

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Dejar la app lista para el uso diario de la familia: instalable en el celular (PWA), accesible fuera de casa por Tailscale con HTTPS, con respaldo diario y restauración probada, y con los datos iniciales cargados desde el Excel del usuario.

**Architecture:** La PWA son tres vistas públicas de `apps/core` (manifiesto, service worker y página sin conexión) más íconos PNG en `static/`. El respaldo es un ZIP propio (manifiesto + `dumpdata` + archivos de `media/`) creado y restaurado con comandos de Django, envueltos en scripts de PowerShell para el Programador de tareas de Windows. La importación del Excel es un módulo de `apps/importacion` que lee el libro con openpyxl, valida el formato antes de escribir y solo crea lo que falta, dentro de una transacción que por omisión se revierte (simulación).

**Tech Stack:** Django 5.2, PostgreSQL 17, Docker Compose, openpyxl (nuevo), Pillow solo para generar los íconos una vez (no es dependencia), PowerShell 5.1, Tailscale Serve.

**Spec:** `docs/DEF.md` (RNF-01, RNF-04, RNF-06, RF-DAT-01, RF-DAT-02, RF-ACC-02, RF-ACC-04, criterio de aceptación 5) y `docs/ARQUITECTURA.md` (§7 despliegue, ADR-07, seguridad).

## Decisiones de este plan (para revisión del usuario)

1. **Tasas de mercado y conceptos (RF-ACC-02) salen de tu Excel**, con la importación de las tareas 6 y 7. No se copia al repositorio ningún dato de la plantilla.
2. **El respaldo es un ZIP propio** (datos en JSON y PDFs), hecho con comandos de Django, no con `pg_dump`. Se prueba automáticamente en cada push y no necesita instalar `pg_dump` 17 en la imagen. Se guarda en la carpeta que indiques (de preferencia dentro de OneDrive), sin cifrar, como define la arquitectura. Se conservan los 30 más recientes.
3. **Restaurar reemplaza todo** y pide confirmación. Antes guarda automáticamente un respaldo de seguridad de los datos actuales, y si algo falla la base queda como estaba.
4. **Sin conexión, la app no muestra páginas guardadas**, solo el aviso «Sin conexión». Así nunca ves datos financieros viejos. No hay captura sin conexión en la v1.
5. **La importación del Excel solo crea lo que falta.** Nunca modifica lo que ya existe, salvo el catálogo global de tasas. Por omisión solo simula y muestra conteos; guarda solo con `--aplicar`.
6. **No se importan las hojas mensuales 01–12.** Están vacías salvo los ingresos extra de octubre, que se capturan en la app como movimientos.
7. **Uso diario en «modo producción»** (gunicorn, `DJANGO_DEBUG=0`): `docker compose -f docker-compose.yml up -d`. El modo desarrollo sigue siendo `docker compose up -d`.

## Global Constraints

- Código, nombres, mensajes y comentarios en español (como el resto del repo); textos para el usuario en español de México.
- Montos y tasas siempre en `Decimal` (RNF-05); `DINERO = max_digits 12, 2 decimales`, `TASA = max_digits 7, 4 decimales`.
- Nunca datos personales en el repositorio ni en pruebas: las pruebas usan un Excel **ficticio** generado en `tmp_path`; el Excel real (`..\2026\documentos\`) solo se lee en la verificación manual de la tarea 7 y solo se imprimen **conteos**.
- Las pruebas no escriben fuera de `tmp_path` (`MEDIA_ROOT` y `RESPALDOS_DIR` temporales).
- Todo se corre dentro de Docker desde `app_finanzas/`: `docker compose run --rm web pytest`, `... ruff check .`, `... ruff format --check .`.
- Ruff: `line-length = 100`; reglas `E, F, W, I, UP, B, DJ, SIM`; `known-first-party = ["apps", "finanzas"]`.
- Commit solo con pruebas, `ruff check` y `ruff format --check` en verde.
- Los scripts `.ps1` deben funcionar en Windows PowerShell 5.1 (sin `&&`, sin `??`).

## Review Focus

1. **Respaldo dañado, truncado, de otra app o de una versión más nueva:** restaurarlo debe dar un mensaje claro y dejar la base exactamente como estaba (tarea 4).
2. **ZIP de respaldo con rutas que salen de `media/`** (`../`, absolutas): se rechaza antes de tocar la base o los archivos (tarea 4).
3. **Excel de otra versión de la plantilla** (hoja faltante, categorías en otro orden) **o archivo que no es .xlsx:** error claro y nada guardado (tarea 6).
4. **Importar el Excel dos veces, o encima de datos capturados a mano:** no duplica ni sobrescribe (tareas 6 y 7).
5. **Sin conexión, la PWA no muestra una página financiera guardada** (datos viejos o de otra sesión): siempre el aviso «Sin conexión» (tarea 1).

---

### Task 1: PWA instalable

**Files:**
- Create: `apps/core/pwa.py`
- Create: `templates/pwa/sw.js`
- Create: `templates/pwa/sin_conexion.html`
- Create: `scripts/generar_iconos.py`
- Create: `static/iconos/icono-192.png`, `icono-512.png`, `icono-maskable-512.png`, `icono-180.png` (generados)
- Modify: `apps/core/urls.py`
- Modify: `templates/base.html` (`<head>`)
- Modify: `static/js/app.js` (al final)
- Test: `tests/core/test_core_pwa.py`

**Interfaces:**
- Consumes: nada de otras tareas.
- Produces: rutas públicas `/manifest.webmanifest` (name `manifiesto`), `/sw.js` (name `service_worker`), `/sin-conexion/` (name `sin_conexion`); íconos en `static/iconos/`.

- [ ] **Step 1: Write the failing tests**

`tests/core/test_core_pwa.py` (completo):

```python
import json
import struct

import pytest
from django.conf import settings
from django.contrib.staticfiles import finders
from django.template.loader import render_to_string

pytestmark = pytest.mark.django_db


def tamano_png(ruta):
    with open(ruta, "rb") as archivo:
        cabecera = archivo.read(24)
    assert cabecera[:8] == b"\x89PNG\r\n\x1a\n"
    return struct.unpack(">II", cabecera[16:24])


def test_manifiesto_publico_con_datos_para_instalar(client):
    respuesta = client.get("/manifest.webmanifest")

    assert respuesta.status_code == 200
    assert respuesta["Content-Type"] == "application/manifest+json"
    datos = json.loads(respuesta.content)
    assert datos["name"] == "Finanzas familiares"
    assert datos["start_url"] == "/"
    assert datos["display"] == "standalone"
    assert {icono["sizes"] for icono in datos["icons"]} >= {"192x192", "512x512"}
    assert any(icono["purpose"] == "maskable" for icono in datos["icons"])


def test_iconos_del_manifiesto_existen_con_su_tamano(client):
    datos = json.loads(client.get("/manifest.webmanifest").content)

    for icono in datos["icons"]:
        ruta = finders.find(icono["src"].removeprefix(settings.STATIC_URL))
        lado = int(icono["sizes"].split("x")[0])
        assert ruta, icono["src"]
        assert tamano_png(ruta) == (lado, lado)


def test_icono_para_iphone():
    assert tamano_png(finders.find("iconos/icono-180.png")) == (180, 180)


def test_service_worker_en_la_raiz_sin_cache(client):
    respuesta = client.get("/sw.js")

    assert respuesta.status_code == 200
    assert respuesta["Content-Type"].startswith("application/javascript")
    assert "no-cache" in respuesta["Cache-Control"]
    assert respuesta["Service-Worker-Allowed"] == "/"
    codigo = respuesta.content.decode()
    assert 'const SIN_CONEXION = "/sin-conexion/";' in codigo
    assert '"/static/css/app.css"' in codigo
    assert "&quot;" not in codigo


def test_sin_conexion_nunca_muestra_una_pagina_guardada(client):
    codigo = client.get("/sw.js").content.decode()

    # Las páginas (datos financieros) van siempre a la red; sin red, solo el aviso.
    assert 'solicitud.mode === "navigate"' in codigo
    assert "fetch(solicitud).catch(() => caches.match(SIN_CONEXION))" in codigo


def test_pagina_sin_conexion_publica(client):
    respuesta = client.get("/sin-conexion/")

    assert respuesta.status_code == 200
    assert "Sin conexión" in respuesta.content.decode()


def test_base_enlaza_manifiesto_e_iconos(rf, django_user_model):
    solicitud = rf.get("/")
    solicitud.user = django_user_model(email="x@example.com")
    solicitud.hogar = None

    html = render_to_string("base.html", request=solicitud)

    assert '<link rel="manifest" href="/manifest.webmanifest">' in html
    assert '<meta name="theme-color" content="#059669">' in html
    assert "iconos/icono-180.png" in html


def test_app_js_registra_el_service_worker():
    codigo = (settings.BASE_DIR / "static" / "js" / "app.js").read_text(encoding="utf-8")

    assert 'navigator.serviceWorker.register("/sw.js")' in codigo
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `docker compose run --rm web pytest tests/core/test_core_pwa.py -q`
Expected: 8 failed (404 en las rutas, íconos inexistentes, textos ausentes).

- [ ] **Step 3: Generar los íconos**

`scripts/generar_iconos.py` (completo):

```python
"""Genera los íconos PNG de la PWA. Se corre una vez; los PNG quedan en el repositorio.

docker run --rm -v "${PWD}:/app" -w /app ghcr.io/astral-sh/uv:python3.12-bookworm-slim \
    uv run --no-project --with pillow python scripts/generar_iconos.py
"""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

VERDE = (5, 150, 105)  # emerald-600, el color de la navegación
BLANCO = (255, 255, 255)
DESTINO = Path(__file__).resolve().parent.parent / "static" / "iconos"


def icono(lado, *, redondeado, escala_texto):
    if redondeado:
        imagen = Image.new("RGBA", (lado, lado), (0, 0, 0, 0))
        ImageDraw.Draw(imagen).rounded_rectangle(
            (0, 0, lado - 1, lado - 1), radius=lado // 5, fill=VERDE
        )
    else:
        imagen = Image.new("RGB", (lado, lado), VERDE)
    fuente = ImageFont.load_default(size=int(lado * escala_texto))
    ImageDraw.Draw(imagen).text((lado / 2, lado / 2), "$", font=fuente, fill=BLANCO, anchor="mm")
    return imagen


def main():
    DESTINO.mkdir(parents=True, exist_ok=True)
    icono(192, redondeado=True, escala_texto=0.62).save(DESTINO / "icono-192.png")
    icono(512, redondeado=True, escala_texto=0.62).save(DESTINO / "icono-512.png")
    # Maskable: fondo completo y el símbolo dentro de la zona segura (80 % central).
    icono(512, redondeado=False, escala_texto=0.45).save(DESTINO / "icono-maskable-512.png")
    # iPhone no usa transparencia: fondo completo.
    icono(180, redondeado=False, escala_texto=0.6).save(DESTINO / "icono-180.png")


if __name__ == "__main__":
    main()
```

Run (Git Bash): `MSYS_NO_PATHCONV=1 docker run --rm -v "$(pwd -W):/app" -w /app ghcr.io/astral-sh/uv:python3.12-bookworm-slim uv run --no-project --with pillow python scripts/generar_iconos.py && ls static/iconos`
Expected: `icono-180.png  icono-192.png  icono-512.png  icono-maskable-512.png`. Abre uno con la herramienta Read para confirmar que se ve un «$» blanco sobre verde.

- [ ] **Step 4: Vistas, plantillas y rutas**

`apps/core/pwa.py` (completo):

```python
"""PWA (RNF-01): manifiesto, service worker y página sin conexión.

Son públicas: el navegador las pide sin la sesión del usuario.
"""

import json

from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import render
from django.templatetags.static import static
from django.urls import reverse
from django.views.decorators.cache import cache_control
from django.views.decorators.http import require_GET

# Súbela cuando cambie ARCHIVOS_SIN_CONEXION, para que los celulares descarten la caché vieja.
VERSION_CACHE = "1"
COLOR_TEMA = "#059669"  # emerald-600, el color de la navegación
COLOR_FONDO = "#f8fafc"  # slate-50, el fondo de la app
ICONOS = [
    ("iconos/icono-192.png", 192, "any"),
    ("iconos/icono-512.png", 512, "any"),
    ("iconos/icono-maskable-512.png", 512, "maskable"),
]
ARCHIVOS_SIN_CONEXION = [
    "css/app.css",
    "vendor/htmx-2.0.11.min.js",
    "js/app.js",
    "iconos/icono-192.png",
]


@require_GET
def manifiesto(request):
    datos = {
        "name": "Finanzas familiares",
        "short_name": "Finanzas",
        "lang": "es-MX",
        "start_url": "/",
        "scope": "/",
        "display": "standalone",
        "background_color": COLOR_FONDO,
        "theme_color": COLOR_TEMA,
        "icons": [
            {"src": static(ruta), "sizes": f"{lado}x{lado}", "type": "image/png", "purpose": uso}
            for ruta, lado, uso in ICONOS
        ],
    }
    return JsonResponse(
        datos,
        content_type="application/manifest+json",
        json_dumps_params={"ensure_ascii": False},
    )


@require_GET
@cache_control(no_cache=True)
def service_worker(request):
    respuesta = render(
        request,
        "pwa/sw.js",
        {
            "cache": f"finanzas-{VERSION_CACHE}",
            "sin_conexion": reverse("sin_conexion"),
            "prefijo_estaticos": settings.STATIC_URL,
            "precarga": json.dumps([static(ruta) for ruta in ARCHIVOS_SIN_CONEXION]),
        },
        content_type="application/javascript; charset=utf-8",
    )
    respuesta["Service-Worker-Allowed"] = "/"
    return respuesta


@require_GET
def sin_conexion(request):
    return render(request, "pwa/sin_conexion.html")
```

`templates/pwa/sw.js` (completo):

```javascript
{% autoescape off %}// Service worker de Finanzas (RNF-01). Lo genera apps/core/pwa.py.
// Las páginas van siempre a la red: los datos financieros nunca se muestran desde caché.
const CACHE = "{{ cache }}";
const SIN_CONEXION = "{{ sin_conexion }}";
const ESTATICOS = "{{ prefijo_estaticos }}";
const PRECARGA = {{ precarga }};

self.addEventListener("install", (evento) => {
  evento.waitUntil(
    caches.open(CACHE)
      .then((cache) => cache.addAll([SIN_CONEXION, ...PRECARGA]))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (evento) => {
  evento.waitUntil(
    caches.keys()
      .then((nombres) => Promise.all(
        nombres.filter((nombre) => nombre !== CACHE).map((nombre) => caches.delete(nombre))
      ))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (evento) => {
  const solicitud = evento.request;
  const url = new URL(solicitud.url);
  if (solicitud.method !== "GET" || url.origin !== self.location.origin) return;

  if (solicitud.mode === "navigate") {
    // Páginas: de la red; sin conexión, solo el aviso (nunca una página guardada).
    evento.respondWith(fetch(solicitud).catch(() => caches.match(SIN_CONEXION)));
    return;
  }
  if (url.pathname.startsWith(ESTATICOS)) {
    // Estilos, scripts e íconos: de la red y, sin conexión, la última copia guardada.
    evento.respondWith(
      fetch(solicitud)
        .then((respuesta) => {
          if (respuesta.ok) {
            const copia = respuesta.clone();
            caches.open(CACHE).then((cache) => cache.put(solicitud, copia));
          }
          return respuesta;
        })
        .catch(() => caches.match(solicitud))
    );
  }
});
{% endautoescape %}
```

`templates/pwa/sin_conexion.html` (completo):

```html
{% load static %}<!doctype html>
<html lang="es-MX">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Sin conexión · Finanzas</title>
  <link rel="stylesheet" href="{% static 'css/app.css' %}">
</head>
<body class="flex min-h-screen items-center justify-center bg-slate-50 p-6 text-slate-900">
  <main class="max-w-sm space-y-4 text-center">
    <h1 class="text-xl font-semibold">Sin conexión</h1>
    <p class="text-slate-600">
      La app necesita conectarse a tu PC. Revisa que esté encendida y que estés en la red de casa
      o con Tailscale activo.
    </p>
    <button type="button" onclick="location.reload()"
            class="rounded-lg bg-emerald-600 px-4 py-2 font-medium text-white">Reintentar</button>
  </main>
</body>
</html>
```

En `apps/core/urls.py`, agregar el import `from apps.core import pwa, vistas` (en lugar de `from apps.core import vistas`) y estas rutas al inicio de `urlpatterns`:

```python
    path("manifest.webmanifest", pwa.manifiesto, name="manifiesto"),
    path("sw.js", pwa.service_worker, name="service_worker"),
    path("sin-conexion/", pwa.sin_conexion, name="sin_conexion"),
```

En `templates/base.html`, agregar después de `<title>…</title>`:

```html
  <link rel="manifest" href="{% url 'manifiesto' %}">
  <meta name="theme-color" content="#059669">
  <link rel="icon" type="image/png" sizes="192x192" href="{% static 'iconos/icono-192.png' %}">
  <link rel="apple-touch-icon" href="{% static 'iconos/icono-180.png' %}">
  <meta name="apple-mobile-web-app-title" content="Finanzas">
```

En `static/js/app.js`, agregar al final:

```javascript

// PWA: el service worker permite instalar la app y muestra un aviso sin conexión.
if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => navigator.serviceWorker.register("/sw.js"));
}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `docker compose run --rm web pytest tests/core/test_core_pwa.py -q`
Expected: 8 passed.

- [ ] **Step 6: Recompilar estilos y suite completa**

Run: `docker compose run --rm css` y luego `docker compose run --rm web pytest -q`, `docker compose run --rm web ruff check --no-cache .`, `docker compose run --rm web ruff format --check .`
Expected: todo en verde.

- [ ] **Step 7: Commit**

```bash
git add apps/core/pwa.py apps/core/urls.py templates/pwa templates/base.html static/js/app.js static/iconos scripts/generar_iconos.py tests/core/test_core_pwa.py
git commit -m "feat(pwa): manifiesto, service worker, página sin conexión e íconos (RNF-01)"
```

---

### Task 2: Uso diario y acceso con Tailscale

**Files:**
- Modify: `.env.example`
- Modify: `README.md` (nueva sección «Uso diario y acceso desde el celular»)
- Test: `tests/test_uso_diario.py`

**Interfaces:**
- Consumes: rutas de la PWA de la tarea 1 (`/manifest.webmanifest`, `/sw.js`, `/sin-conexion/`, `static/iconos/`).
- Produces: variables documentadas `DJANGO_DEBUG=0`, `DJANGO_ALLOWED_HOSTS`, `DJANGO_CSRF_TRUSTED_ORIGINS` (ya existían en `finanzas/settings.py`).

- [ ] **Step 1: Write the failing test**

`tests/test_uso_diario.py` (completo):

```python
from django.conf import settings


def test_env_de_ejemplo_listo_para_uso_diario():
    texto = (settings.BASE_DIR / ".env.example").read_text(encoding="utf-8")

    assert "DJANGO_DEBUG=0" in texto
    assert "DJANGO_CSRF_TRUSTED_ORIGINS=" in texto
    assert ".ts.net" in texto


def test_readme_explica_tailscale_y_el_modo_de_uso_diario():
    texto = (settings.BASE_DIR / "README.md").read_text(encoding="utf-8")

    assert "## Uso diario y acceso desde el celular" in texto
    assert "tailscale serve --bg 8000" in texto
    assert "docker compose -f docker-compose.yml up -d --build" in texto
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker compose run --rm web pytest tests/test_uso_diario.py -q`
Expected: 2 failed.

- [ ] **Step 3: Actualizar `.env.example`**

Reemplazar las tres primeras líneas (`DJANGO_DEBUG=1`, `DJANGO_SECRET_KEY=…`, `DJANGO_ALLOWED_HOSTS=…`) por:

```
# Uso diario: 0. Al desarrollar, docker-compose.override.yml ya activa el modo depuración.
DJANGO_DEBUG=0
# Genera una con: docker compose run --rm web python -c "import secrets; print(secrets.token_urlsafe(50))"
DJANGO_SECRET_KEY=cambia-esto-por-una-clave-larga-y-aleatoria
# Agrega la IP de tu PC en la red de casa y el nombre de Tailscale (ej. mi-pc.tail1234.ts.net).
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1
# Con Tailscale, la dirección https completa (ej. https://mi-pc.tail1234.ts.net).
DJANGO_CSRF_TRUSTED_ORIGINS=
```

- [ ] **Step 4: Sección del README**

Agregar después de la sección «## Primer uso» (antes de «## Importar documentos con IA»):

````markdown
## Uso diario y acceso desde el celular

**Modo de uso diario** (gunicorn, sin depuración). En `.env`: `DJANGO_DEBUG=0` y una `DJANGO_SECRET_KEY` larga y aleatoria. Luego:

```powershell
docker compose -f docker-compose.yml up -d --build
```

Para volver al modo desarrollo: `docker compose up -d`. Después de actualizar el código (`git pull`), repite el comando de uso diario.

**Fuera de casa con Tailscale** (HTTPS sin abrir puertos del router):

1. Instala Tailscale en la PC y en el celular con la misma cuenta.
2. En https://login.tailscale.com/admin/dns activa **MagicDNS** y **HTTPS Certificates**.
3. En la PC (PowerShell): `tailscale serve --bg 8000`. Muestra tu dirección, por ejemplo `https://mi-pc.tail1234.ts.net`.
4. En `.env` agrega el nombre a `DJANGO_ALLOWED_HOSTS` (`localhost,127.0.0.1,mi-pc.tail1234.ts.net`) y la dirección completa a `DJANGO_CSRF_TRUSTED_ORIGINS` (`https://mi-pc.tail1234.ts.net`). Reinicia con el comando de uso diario.
5. En el celular abre esa dirección e instala la app: en Android, menú ⋮ → **Instalar app**; en iPhone (Safari), Compartir → **Agregar a inicio**.

La app solo responde mientras la PC está encendida. Sin conexión verás el aviso «Sin conexión», nunca datos guardados.
````

- [ ] **Step 5: Run test to verify it passes**

Run: `docker compose run --rm web pytest tests/test_uso_diario.py -q`
Expected: 2 passed.

- [ ] **Step 6: Verificar el modo de uso diario en una instalación aparte**

Corre la app en modo producción en un proyecto de Compose separado (`finanzas-prueba`, con su propia base), para no tocar la del usuario:

```bash
MSYS_NO_PATHCONV=1 docker compose -p finanzas-prueba -f docker-compose.yml run -d --name finanzas-prueba-web -p 8001:8000 -e DJANGO_DEBUG=0 -e DJANGO_SECRET_KEY=prueba-uso-diario -e DJANGO_ALLOWED_HOSTS=localhost web
for i in $(seq 60); do curl -sf http://localhost:8001/salud/ >/dev/null && break; sleep 2; done
for ruta in /salud/ /manifest.webmanifest /sw.js /sin-conexion/ /static/iconos/icono-192.png /static/css/app.css /entrar/; do curl -s -o /dev/null -w "%{http_code} $ruta\n" "http://localhost:8001$ruta"; done
docker rm -f finanzas-prueba-web; docker compose -p finanzas-prueba down -v
```

Expected: siete líneas `200 …`. Este paso confirma que, sin depuración, gunicorn y WhiteNoise sirven el manifiesto, el service worker y los íconos.

- [ ] **Step 7: Suite completa y commit**

Run: `docker compose run --rm web pytest -q` y los dos `ruff`. Expected: verde.

```bash
git add .env.example README.md tests/test_uso_diario.py
git commit -m "docs: uso diario en modo producción y acceso con Tailscale (RNF-04)"
```

---

### Task 3: Respaldo (RF-DAT-01)

**Files:**
- Create: `apps/core/respaldo.py`
- Create: `apps/core/management/__init__.py`, `apps/core/management/commands/__init__.py` (vacíos)
- Create: `apps/core/management/commands/respaldar.py`
- Modify: `finanzas/settings.py` (agregar `RESPALDOS_DIR`)
- Modify: `docker-compose.yml` (servicio `web`)
- Modify: `.env.example`, `.gitignore`, `.dockerignore`
- Modify: `tests/conftest.py` (fixture autouse `respaldos_temporales`)
- Test: `tests/core/test_core_respaldo.py`

**Interfaces:**
- Consumes: nada de otras tareas.
- Produces (en `apps.core.respaldo`):
  - `FORMATO = 1`, `PREFIJO = "finanzas-"`
  - `class ErrorRespaldo(Exception)`: mensaje para el usuario.
  - `migraciones_aplicadas() -> dict[str, list[str]]`
  - `crear_respaldo(carpeta=None, *, prefijo=PREFIJO, conservar=None) -> pathlib.Path`
  - `rotar(carpeta, conservar: int) -> list[pathlib.Path]` (los borrados)
  - Comando `respaldar [--carpeta RUTA] [--conservar N]`.
  - `settings.RESPALDOS_DIR: pathlib.Path`.

- [ ] **Step 1: Fixture de carpeta temporal**

En `tests/conftest.py`, agregar después de la fixture `media_temporal`:

```python
@pytest.fixture(autouse=True)
def respaldos_temporales(settings, tmp_path):
    """Los respaldos de las pruebas van a una carpeta temporal."""
    settings.RESPALDOS_DIR = tmp_path / "respaldos"
```

- [ ] **Step 2: Write the failing tests**

`tests/core/test_core_respaldo.py` (completo):

```python
import json
import re
import zipfile

import pytest
from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.core.management import call_command

from apps.core.respaldo import ErrorRespaldo, crear_respaldo, rotar

pytestmark = pytest.mark.django_db


def test_respaldo_incluye_manifiesto_datos_y_archivos(catalogo):
    default_storage.save("documentos/1/abc.pdf", ContentFile(b"%PDF-1.4 prueba"))

    destino = crear_respaldo()

    with zipfile.ZipFile(destino) as respaldo:
        nombres = set(respaldo.namelist())
        manifiesto = json.loads(respaldo.read("manifiesto.json"))
        datos = json.loads(respaldo.read("datos.json"))
    assert {"manifiesto.json", "datos.json", "media/documentos/1/abc.pdf"} <= nombres
    assert manifiesto["formato"] == 1
    assert "0001_initial" in manifiesto["migraciones"]["catalogos"]
    assert manifiesto["registros"]["catalogos.cuenta"] == 4
    assert any(registro["model"] == "core.usuario" for registro in datos)
    excluidos = ("contenttypes.", "auth.permission", "sessions.", "django_q.")
    assert not any(registro["model"].startswith(excluidos) for registro in datos)


def test_nombre_con_fecha_y_sin_archivos_a_medias(hogar):
    destino = crear_respaldo()

    assert destino.parent == settings.RESPALDOS_DIR
    assert re.fullmatch(r"finanzas-\d{8}-\d{6}\.zip", destino.name)
    assert list(settings.RESPALDOS_DIR.glob("*.tmp")) == []


def test_rotacion_conserva_los_mas_recientes_y_los_de_seguridad(tmp_path):
    for dia in range(1, 6):
        (tmp_path / f"finanzas-2026100{dia}-030000.zip").write_bytes(b"x")
    seguridad = tmp_path / "finanzas-antes-de-restaurar-20261001-030000.zip"
    seguridad.write_bytes(b"x")

    borrados = rotar(tmp_path, 3)

    assert len(borrados) == 2
    assert sorted(p.name for p in tmp_path.glob("finanzas-2*.zip")) == [
        "finanzas-20261003-030000.zip",
        "finanzas-20261004-030000.zip",
        "finanzas-20261005-030000.zip",
    ]
    assert seguridad.exists()


def test_carpeta_invalida_da_error_claro(hogar, tmp_path):
    archivo = tmp_path / "no-es-carpeta"
    archivo.write_text("x")

    with pytest.raises(ErrorRespaldo, match="carpeta de respaldos"):
        crear_respaldo(archivo / "respaldos")


def test_comando_respaldar(hogar, capsys):
    call_command("respaldar", conservar=2)

    assert "Respaldo creado" in capsys.readouterr().out
    assert len(list(settings.RESPALDOS_DIR.glob("finanzas-*.zip"))) == 1
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `docker compose run --rm web pytest tests/core/test_core_respaldo.py -q`
Expected: error de colección `ModuleNotFoundError: No module named 'apps.core.respaldo'`.

- [ ] **Step 4: Implementación**

`apps/core/respaldo.py` (completo):

```python
"""Respaldo y restauración de todos los datos (RF-DAT-01, RF-DAT-02, RNF-06).

Un respaldo es un ZIP con:
- manifiesto.json: formato, fecha, migraciones aplicadas y registros por modelo;
- datos.json: la base de datos (dumpdata con llaves naturales);
- media/…: los archivos subidos (PDFs importados).
"""

import io
import json
import os
import zipfile
from collections import Counter
from pathlib import Path

from django.conf import settings
from django.core.management import call_command
from django.db import connection, transaction
from django.db.migrations.recorder import MigrationRecorder
from django.utils import timezone

FORMATO = 1
PREFIJO = "finanzas-"
# Tablas que Django vuelve a crear solo o que no son datos del usuario.
EXCLUIR = ["contenttypes", "auth.permission", "sessions", "admin.logentry", "django_q"]


class ErrorRespaldo(Exception):
    """Error con un mensaje para el usuario."""


def migraciones_aplicadas():
    """{app: [migraciones]} aplicadas en la base actual."""
    aplicadas = {}
    for app, nombre in MigrationRecorder(connection).applied_migrations():
        aplicadas.setdefault(app, []).append(nombre)
    return {app: sorted(nombres) for app, nombres in sorted(aplicadas.items())}


def _volcar_base():
    salida = io.StringIO()
    call_command("dumpdata", exclude=EXCLUIR, use_natural_foreign_keys=True, stdout=salida)
    return salida.getvalue()


def _archivos_media():
    raiz = Path(settings.MEDIA_ROOT)
    if not raiz.exists():
        return []
    return sorted(ruta for ruta in raiz.rglob("*") if ruta.is_file())


def crear_respaldo(carpeta=None, *, prefijo=PREFIJO, conservar=None):
    """Escribe el ZIP en la carpeta (por omisión RESPALDOS_DIR) y devuelve su ruta."""
    carpeta = Path(carpeta or settings.RESPALDOS_DIR)
    try:
        carpeta.mkdir(parents=True, exist_ok=True)
    except OSError as error:
        raise ErrorRespaldo(f"No se pudo usar la carpeta de respaldos {carpeta}: {error}") from error
    fecha = timezone.localtime()
    destino = carpeta / f"{prefijo}{fecha:%Y%m%d-%H%M%S}.zip"
    temporal = destino.with_name(destino.name + ".tmp")

    externa = connection.in_atomic_block
    with transaction.atomic():
        if not externa:
            # Una sola fotografía de todas las tablas aunque la app se esté usando.
            with connection.cursor() as cursor:
                cursor.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")
        datos = _volcar_base()
        manifiesto = {
            "formato": FORMATO,
            "creado_en": fecha.isoformat(),
            "migraciones": migraciones_aplicadas(),
            "registros": dict(sorted(Counter(r["model"] for r in json.loads(datos)).items())),
        }

    try:
        with zipfile.ZipFile(temporal, "w", zipfile.ZIP_DEFLATED) as respaldo:
            respaldo.writestr("manifiesto.json", json.dumps(manifiesto, ensure_ascii=False))
            respaldo.writestr("datos.json", datos)
            for archivo in _archivos_media():
                relativa = archivo.relative_to(settings.MEDIA_ROOT).as_posix()
                respaldo.write(archivo, f"media/{relativa}")
        os.replace(temporal, destino)
    except OSError as error:
        temporal.unlink(missing_ok=True)
        raise ErrorRespaldo(f"No se pudo escribir el respaldo en {carpeta}: {error}") from error

    if conservar:
        rotar(carpeta, conservar)
    return destino


def rotar(carpeta, conservar):
    """Deja solo los `conservar` respaldos diarios más recientes (no toca los de seguridad)."""
    diarios = sorted(Path(carpeta).glob(f"{PREFIJO}[0-9]*.zip"))
    borrados = diarios[:-conservar] if conservar > 0 else []
    for viejo in borrados:
        viejo.unlink()
    return borrados
```

`apps/core/management/commands/respaldar.py` (completo):

```python
from django.core.management.base import BaseCommand, CommandError

from apps.core.respaldo import ErrorRespaldo, crear_respaldo


class Command(BaseCommand):
    help = "Respalda la base de datos y los archivos subidos en un ZIP (RF-DAT-01)."

    def add_arguments(self, parser):
        parser.add_argument("--carpeta", help="Carpeta destino (por omisión RESPALDOS_DIR).")
        parser.add_argument(
            "--conservar",
            type=int,
            default=30,
            help="Cuántos respaldos diarios conservar (0 = todos).",
        )

    def handle(self, *args, carpeta=None, conservar=30, **opciones):
        try:
            destino = crear_respaldo(carpeta, conservar=conservar)
        except ErrorRespaldo as error:
            raise CommandError(str(error)) from error
        kb = destino.stat().st_size // 1024
        self.stdout.write(self.style.SUCCESS(f"Respaldo creado: {destino.name} ({kb} KB)"))
```

En `finanzas/settings.py`, después de `MEDIA_ROOT` (confirma que `from pathlib import Path` ya está importado):

```python
# Respaldos (RF-DAT-01). En Docker es /respaldos, montada desde CARPETA_RESPALDOS del .env.
RESPALDOS_DIR = Path(env("RESPALDOS_DIR", default=str(BASE_DIR / "respaldos")))
```

En `docker-compose.yml`, en el servicio `web`, agregar el bloque `environment` y la segunda línea de `volumes`:

```yaml
    environment:
      RESPALDOS_DIR: /respaldos
    volumes:
      - media:/app/media
      - ${CARPETA_RESPALDOS:-./respaldos}:/respaldos
```

En `.env.example`, agregar al final:

```
# Carpeta de la PC para los respaldos; de preferencia dentro de OneDrive y FUERA del repositorio.
# Ejemplo: CARPETA_RESPALDOS=C:/Users/tu-usuario/OneDrive/Respaldos/finanzas
CARPETA_RESPALDOS=./respaldos
```

En `.gitignore`, agregar en la sección de datos personales `respaldos/` y `respaldos.log`. En `.dockerignore`, la lista blanca ya deja fuera `respaldos/`; agregar igualmente `**/respaldos` en la red de seguridad.

- [ ] **Step 5: Run tests to verify they pass**

Run: `docker compose run --rm web pytest tests/core/test_core_respaldo.py -q`
Expected: 5 passed.

- [ ] **Step 6: Respaldo real (fuera de una transacción de prueba)**

Run: `docker compose up -d web` y luego `docker compose exec -T web python manage.py respaldar --conservar 0` y `ls respaldos`
Expected: `Respaldo creado: finanzas-AAAAMMDD-HHMMSS.zip (N KB)`, y el archivo aparece en `respaldos/` de la PC. Esto ejercita `SET TRANSACTION ISOLATION LEVEL REPEATABLE READ`, que las pruebas no ejecutan porque corren dentro de una transacción.

- [ ] **Step 7: Suite completa y commit**

Run: `docker compose run --rm web pytest -q` y los dos `ruff`. Expected: verde.

```bash
git add apps/core/respaldo.py apps/core/management finanzas/settings.py docker-compose.yml .env.example .gitignore .dockerignore tests/conftest.py tests/core/test_core_respaldo.py
git commit -m "feat(respaldo): comando respaldar con ZIP de datos y archivos, y rotación (RF-DAT-01)"
```

---

### Task 4: Restauración (RF-DAT-02)

**Files:**
- Modify: `apps/core/respaldo.py` (agregar lectura, validación y restauración)
- Create: `apps/core/management/commands/restaurar.py`
- Test: `tests/core/test_core_restauracion.py`

**Interfaces:**
- Consumes: `crear_respaldo`, `migraciones_aplicadas`, `ErrorRespaldo`, `FORMATO`, `PREFIJO` (tarea 3).
- Produces (en `apps.core.respaldo`):
  - `@dataclass(frozen=True) class Restauracion: registros: int; archivos: int; seguridad: Path | None`
  - `leer_respaldo(ruta) -> tuple[dict, str, dict[str, bytes]]` (manifiesto, JSON de datos, archivos de media por ruta relativa); valida todo sin tocar nada.
  - `restaurar_respaldo(ruta) -> Restauracion`
  - Comando `restaurar ARCHIVO --confirmar` (si `ARCHIVO` no existe tal cual, se busca en `RESPALDOS_DIR`).

- [ ] **Step 1: Write the failing tests**

`tests/core/test_core_restauracion.py` (completo):

```python
import json
import zipfile
from decimal import Decimal as D

import pytest
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.catalogos.models import Cuenta, Persona
from apps.core.models import Membresia
from apps.core.respaldo import ErrorRespaldo, crear_respaldo, leer_respaldo, restaurar_respaldo

# Restaurar vacía y recarga la base (flush + loaddata): pruebas con transacciones reales.
pytestmark = pytest.mark.django_db(transaction=True)


def zip_con(ruta, **contenido):
    with zipfile.ZipFile(ruta, "w") as archivo:
        for nombre, datos in contenido.items():
            archivo.writestr(nombre.replace("__", "/"), datos)
    return ruta


def test_restaurar_recupera_datos_y_archivos(catalogo, hogar, usuario):
    default_storage.save("documentos/1/abc.pdf", ContentFile(b"%PDF-1.4 prueba"))
    respaldo = crear_respaldo()
    Cuenta.objects.filter(pk=catalogo.tarjeta.pk).update(saldo_actual=D("1"))
    Persona.objects.create(hogar=hogar, nombre="Nueva", parentesco="hija")
    default_storage.delete("documentos/1/abc.pdf")

    resultado = restaurar_respaldo(respaldo)

    catalogo.tarjeta.refresh_from_db()
    assert catalogo.tarjeta.saldo_actual == D("6839.01")
    assert not Persona.objects.filter(nombre="Nueva").exists()
    assert Membresia.objects.get().usuario.email == usuario.email
    assert get_user_model().objects.get().check_password("clave-segura-123")
    assert default_storage.open("documentos/1/abc.pdf").read() == b"%PDF-1.4 prueba"
    assert resultado.archivos == 1
    assert resultado.seguridad.name.startswith("finanzas-antes-de-restaurar-")


def test_instalacion_limpia_sin_respaldo_de_seguridad(catalogo):
    respaldo = crear_respaldo()
    call_command("flush", interactive=False, verbosity=0)

    resultado = restaurar_respaldo(respaldo)

    assert resultado.seguridad is None
    assert Cuenta.objects.count() == 4


def test_archivo_que_no_es_zip_no_toca_la_base(catalogo, tmp_path):
    roto = tmp_path / "roto.zip"
    roto.write_bytes(b"no es un zip")

    with pytest.raises(ErrorRespaldo, match="No se pudo abrir"):
        restaurar_respaldo(roto)
    assert Cuenta.objects.count() == 4


def test_zip_de_otra_cosa(tmp_path):
    otro = zip_con(tmp_path / "otro.zip", **{"hola.txt": "hola"})

    with pytest.raises(ErrorRespaldo, match="no es un respaldo de Finanzas"):
        leer_respaldo(otro)


def test_rutas_que_salen_de_media_se_rechazan(tmp_path):
    malo = tmp_path / "malo.zip"
    with zipfile.ZipFile(malo, "w") as archivo:
        archivo.writestr("manifiesto.json", json.dumps({"formato": 1, "migraciones": {}}))
        archivo.writestr("datos.json", "[]")
        archivo.writestr("media/../../finanzas/settings.py", "x")

    with pytest.raises(ErrorRespaldo, match="ruta no permitida"):
        leer_respaldo(malo)


def test_respaldo_de_una_version_mas_nueva(catalogo, tmp_path):
    manifiesto = {"formato": 1, "migraciones": {"catalogos": ["9999_futuro"]}}
    nuevo = zip_con(
        tmp_path / "nuevo.zip", **{"manifiesto.json": json.dumps(manifiesto), "datos.json": "[]"}
    )

    with pytest.raises(ErrorRespaldo, match="versión más nueva"):
        restaurar_respaldo(nuevo)
    assert Cuenta.objects.count() == 4


def test_datos_invalidos_revierten_todo(catalogo, tmp_path):
    respaldo = crear_respaldo()
    with zipfile.ZipFile(respaldo) as original:
        manifiesto = original.read("manifiesto.json")
    datos = [{"model": "catalogos.cuenta", "pk": 1, "fields": {"hogar": 999999, "nombre": "X",
              "tipo": "debito", "creado_en": "2026-10-09T00:00:00Z",
              "actualizado_en": "2026-10-09T00:00:00Z"}}]  # fmt: skip
    malo = zip_con(
        tmp_path / "malo.zip", **{"manifiesto.json": manifiesto, "datos.json": json.dumps(datos)}
    )

    with pytest.raises(ErrorRespaldo, match="no se cambió nada"):
        restaurar_respaldo(malo)
    assert Cuenta.objects.count() == 4


def test_comando_pide_confirmacion(catalogo, capsys):
    respaldo = crear_respaldo()

    with pytest.raises(CommandError, match="--confirmar"):
        call_command("restaurar", respaldo.name)
    call_command("restaurar", respaldo.name, confirmar=True)

    assert "Restaurado" in capsys.readouterr().out
    assert Cuenta.objects.count() == 4


def test_comando_con_archivo_inexistente():
    with pytest.raises(CommandError, match="No existe el respaldo"):
        call_command("restaurar", "no-existe.zip", confirmar=True)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `docker compose run --rm web pytest tests/core/test_core_restauracion.py -q`
Expected: error de colección `ImportError: cannot import name 'leer_respaldo'`.

- [ ] **Step 3: Implementación**

En `apps/core/respaldo.py`, reemplazar el bloque de imports por:

```python
import io
import json
import os
import tempfile
import zipfile
import zlib
from collections import Counter
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.core.management import call_command
from django.core.serializers.base import DeserializationError
from django.db import DatabaseError, connection, transaction
from django.db.migrations.recorder import MigrationRecorder
from django.utils import timezone
```

y agregar al final del archivo:

```python
@dataclass(frozen=True)
class Restauracion:
    registros: int
    archivos: int
    seguridad: Path | None


def _ruta_permitida(nombre):
    ruta = PurePosixPath(nombre)
    return (
        nombre.startswith("media/")
        and not ruta.is_absolute()
        and ".." not in ruta.parts
        and "\\" not in nombre
    )


def leer_respaldo(ruta):
    """Valida el ZIP y devuelve (manifiesto, datos_json, archivos) sin tocar nada."""
    try:
        respaldo = zipfile.ZipFile(ruta)
    except (OSError, zipfile.BadZipFile) as error:
        raise ErrorRespaldo(f"No se pudo abrir el respaldo: {error}") from error
    with respaldo:
        nombres = respaldo.namelist()
        if "manifiesto.json" not in nombres or "datos.json" not in nombres:
            raise ErrorRespaldo(
                "El archivo no es un respaldo de Finanzas (le falta manifiesto.json o datos.json)."
            )
        medios = [n for n in nombres if n not in ("manifiesto.json", "datos.json")]
        for nombre in medios:
            if not _ruta_permitida(nombre):
                raise ErrorRespaldo(f"El respaldo contiene una ruta no permitida: {nombre}")
        try:
            manifiesto = json.loads(respaldo.read("manifiesto.json"))
            datos = respaldo.read("datos.json").decode("utf-8")
            registros = json.loads(datos)
            archivos = {
                n.removeprefix("media/"): respaldo.read(n) for n in medios if not n.endswith("/")
            }
        except (zipfile.BadZipFile, ValueError, zlib.error, EOFError) as error:
            raise ErrorRespaldo("El respaldo está dañado.") from error
    if not isinstance(manifiesto, dict) or manifiesto.get("formato") != FORMATO:
        raise ErrorRespaldo("El respaldo tiene un formato desconocido.")
    if not isinstance(registros, list):
        raise ErrorRespaldo("El respaldo está dañado.")
    return manifiesto, datos, archivos


def _validar_migraciones(manifiesto):
    actuales = migraciones_aplicadas()
    faltantes = [
        f"{app}.{nombre}"
        for app, nombres in (manifiesto.get("migraciones") or {}).items()
        for nombre in nombres
        if nombre not in actuales.get(app, [])
    ]
    if faltantes:
        raise ErrorRespaldo(
            "El respaldo es de una versión más nueva de la app (faltan migraciones: "
            + ", ".join(faltantes[:5])
            + "). Actualiza el código antes de restaurar."
        )


def _escribir_media(archivos):
    raiz = Path(settings.MEDIA_ROOT)
    for relativa, contenido in archivos.items():
        destino = raiz / relativa
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_bytes(contenido)


def restaurar_respaldo(ruta):
    """Reemplaza TODOS los datos por los del respaldo. Si algo falla, la base queda igual."""
    manifiesto, datos, archivos = leer_respaldo(ruta)
    _validar_migraciones(manifiesto)
    seguridad = None
    if get_user_model().objects.exists():
        seguridad = crear_respaldo(prefijo=f"{PREFIJO}antes-de-restaurar-")
    with tempfile.TemporaryDirectory() as carpeta:
        fixture = Path(carpeta) / "datos.json"  # loaddata reconoce el formato por la extensión
        fixture.write_text(datos, encoding="utf-8")
        try:
            with transaction.atomic():
                call_command("flush", interactive=False, verbosity=0)
                call_command("loaddata", str(fixture), verbosity=0)
        except (DatabaseError, DeserializationError, ValueError) as error:
            raise ErrorRespaldo(
                f"No se pudo cargar el respaldo; no se cambió nada. Detalle: {error}"
            ) from error
    ContentType.objects.clear_cache()  # flush recreó los tipos de contenido con otros ids
    _escribir_media(archivos)
    return Restauracion(
        registros=len(json.loads(datos)), archivos=len(archivos), seguridad=seguridad
    )
```

`apps/core/management/commands/restaurar.py` (completo):

```python
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.core.respaldo import ErrorRespaldo, restaurar_respaldo


class Command(BaseCommand):
    help = "Reemplaza TODOS los datos por los de un respaldo (RF-DAT-02)."

    def add_arguments(self, parser):
        parser.add_argument("archivo", help="Ruta del ZIP o su nombre dentro de RESPALDOS_DIR.")
        parser.add_argument(
            "--confirmar",
            action="store_true",
            help="Confirma que se reemplazarán todos los datos actuales.",
        )

    def handle(self, *args, archivo, confirmar=False, **opciones):
        ruta = Path(archivo)
        if not ruta.exists():
            ruta = Path(settings.RESPALDOS_DIR) / archivo
        if not ruta.is_file():
            raise CommandError(f"No existe el respaldo {archivo}.")
        if not confirmar:
            raise CommandError(
                "Esto reemplaza TODOS los datos actuales por los del respaldo. "
                "Repite el comando con --confirmar."
            )
        try:
            resultado = restaurar_respaldo(ruta)
        except ErrorRespaldo as error:
            raise CommandError(str(error)) from error
        if resultado.seguridad:
            self.stdout.write(f"Respaldo de los datos anteriores: {resultado.seguridad.name}")
        self.stdout.write(
            self.style.SUCCESS(
                f"Restaurado: {resultado.registros} registros y {resultado.archivos} archivos."
            )
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `docker compose run --rm web pytest tests/core/test_core_restauracion.py tests/core/test_core_respaldo.py -q`
Expected: 14 passed.

- [ ] **Step 5: Suite completa y commit**

Run: `docker compose run --rm web pytest -q` y los dos `ruff`. Expected: verde.

```bash
git add apps/core/respaldo.py apps/core/management/commands/restaurar.py tests/core/test_core_restauracion.py
git commit -m "feat(respaldo): comando restaurar validado, atómico y con respaldo de seguridad (RF-DAT-02)"
```

---

### Task 5: Respaldo diario automático y prueba en una instalación limpia

**Files:**
- Create: `scripts/respaldar.ps1`, `scripts/restaurar.ps1`, `scripts/programar_respaldo.ps1`
- Modify: `README.md` (sección «Respaldos»)
- Modify: `docs/ARQUITECTURA.md` (nombres de scripts y nodo del respaldo)
- Test: `tests/test_uso_diario.py` (agregar una prueba)

**Interfaces:**
- Consumes: comandos `respaldar` y `restaurar` (tareas 3 y 4); carpeta `/respaldos` del contenedor `web`.
- Produces: tarea programada «Finanzas - respaldo diario» (la registra el usuario); bitácora `respaldos.log` en `app_finanzas/`.

- [ ] **Step 1: Write the failing test**

Agregar a `tests/test_uso_diario.py`:

```python
def test_scripts_de_respaldo_documentados():
    scripts = settings.BASE_DIR / "scripts"
    readme = (settings.BASE_DIR / "README.md").read_text(encoding="utf-8")

    for nombre in ("respaldar.ps1", "restaurar.ps1", "programar_respaldo.ps1"):
        assert (scripts / nombre).is_file(), nombre
        assert nombre in readme
    assert "RESTAURAR" in (scripts / "restaurar.ps1").read_text(encoding="utf-8")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker compose run --rm web pytest tests/test_uso_diario.py -q`
Expected: 1 failed (`respaldar.ps1`).

- [ ] **Step 3: Scripts**

`scripts/respaldar.ps1` (completo):

```powershell
# Respaldo de Finanzas (RF-DAT-01). Lo ejecuta a diario el Programador de tareas de Windows.
# Uso manual: powershell -ExecutionPolicy Bypass -File scripts\respaldar.ps1
$raiz = Split-Path -Parent $PSScriptRoot
Set-Location $raiz
$bitacora = Join-Path $raiz "respaldos.log"
$salida = & docker compose exec -T web python manage.py respaldar --conservar 30 2>&1 | ForEach-Object { "$_" }
$codigo = $LASTEXITCODE
"$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') codigo=$codigo $($salida -join ' ')" | Add-Content -Encoding UTF8 $bitacora
exit $codigo
```

`scripts/programar_respaldo.ps1` (completo):

```powershell
# Registra (una sola vez) la tarea diaria de respaldo en el Programador de tareas de Windows.
# Uso: powershell -ExecutionPolicy Bypass -File scripts\programar_respaldo.ps1 [-Hora 21:00]
param([string]$Hora = "21:00")
$script = Join-Path $PSScriptRoot "respaldar.ps1"
$accion = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$script`""
$disparador = New-ScheduledTaskTrigger -Daily -At $Hora
# Si la PC estaba apagada a esa hora, corre en cuanto se pueda.
$ajustes = New-ScheduledTaskSettingsSet -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Minutes 30)
Register-ScheduledTask -TaskName "Finanzas - respaldo diario" -Action $accion -Trigger $disparador -Settings $ajustes -Description "Respalda la base de datos y los PDFs de la app Finanzas." -Force | Out-Null
Write-Host "Tarea registrada: respaldo diario a las $Hora. Bitácora: $(Join-Path (Split-Path -Parent $PSScriptRoot) 'respaldos.log')"
```

`scripts/restaurar.ps1` (completo):

```powershell
# Restaura un respaldo (RF-DAT-02). REEMPLAZA todos los datos actuales.
# Uso: powershell -ExecutionPolicy Bypass -File scripts\restaurar.ps1 finanzas-20261009-210000.zip
# El ZIP debe estar en la carpeta de respaldos (CARPETA_RESPALDOS del .env).
param([Parameter(Mandatory = $true)][string]$Archivo)
$raiz = Split-Path -Parent $PSScriptRoot
Set-Location $raiz
$nombre = Split-Path -Leaf $Archivo
$respuesta = Read-Host "Esto reemplaza TODOS los datos actuales por los de $nombre. Escribe RESTAURAR para continuar"
if ($respuesta -cne "RESTAURAR") {
    Write-Host "Cancelado: no se cambió nada."
    exit 1
}
docker compose stop worker
docker compose exec -T web python manage.py restaurar $nombre --confirmar
$codigo = $LASTEXITCODE
docker compose start worker
exit $codigo
```

- [ ] **Step 4: README y arquitectura**

Agregar al final de `README.md`:

````markdown
## Respaldos

Cada respaldo es un ZIP con la base de datos y los PDFs importados. Contiene tus datos personales: guárdalo en una carpeta privada.

1. En `.env`, elige la carpeta (de preferencia dentro de OneDrive y fuera de este repositorio), por ejemplo `CARPETA_RESPALDOS=C:/Users/tu-usuario/OneDrive/Respaldos/finanzas`, y reinicia: `docker compose up -d` (o el comando de uso diario).
2. Respaldo manual: `powershell -ExecutionPolicy Bypass -File scripts\respaldar.ps1`. El resultado queda en `respaldos.log`.
3. Respaldo diario automático (una sola vez): `powershell -ExecutionPolicy Bypass -File scripts\programar_respaldo.ps1 -Hora 21:00`. Se conservan los 30 más recientes.
4. Restaurar: `powershell -ExecutionPolicy Bypass -File scripts\restaurar.ps1 finanzas-AAAAMMDD-HHMMSS.zip` (pide escribir `RESTAURAR`). Antes de reemplazar, guarda un respaldo `finanzas-antes-de-restaurar-…` de los datos actuales. Si el respaldo está dañado o es de una versión más nueva de la app, no cambia nada.

En una PC nueva: instala Docker, clona el repositorio, crea `.env`, levanta la app y restaura el último respaldo (no hace falta `crear_hogar`).
````

En `docs/ARQUITECTURA.md`, reemplazar:
- `BK["<b>backup</b> (perfil opcional)<br/>pg_dump + copia de media"]` por `BK["<b>respaldo</b> (Programador de tareas)<br/>manage.py respaldar → ZIP con datos y PDFs"]`
- `(backup.ps1, restore.ps1, deploy.ps1)` por `(respaldar.ps1, restaurar.ps1, programar_respaldo.ps1, importar_excel.ps1)`
- `` `scripts/backup.ps1` `` por `` `scripts/respaldar.ps1` ``

Run: `grep -n "backup.ps1\|pg_dump" docs/ARQUITECTURA.md`
Expected: sin resultados.

- [ ] **Step 5: Run test to verify it passes**

Run: `docker compose run --rm web pytest tests/test_uso_diario.py -q`
Expected: 3 passed.

- [ ] **Step 6: Script de respaldo real**

Run (PowerShell): `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\respaldar.ps1; echo "exit=$LASTEXITCODE"; Get-Content respaldos.log -Tail 1`
Expected: `exit=0` y una línea `… codigo=0 Respaldo creado: finanzas-….zip (N KB)`.

- [ ] **Step 7: Restaurar en una instalación limpia (criterio de aceptación 5)**

Restaura el respaldo recién creado en un proyecto de Compose aparte (base y media nuevas) y compara los conteos con la instalación real. Solo se imprimen conteos.

```bash
NOMBRE=$(ls -1 respaldos/finanzas-2*.zip | tail -1 | xargs -n1 basename)
CONTEO='import json; from pathlib import Path; from django.apps import apps; from django.conf import settings; print(json.dumps({m._meta.label_lower: m.objects.count() for m in apps.get_models() if m._meta.app_label in ("core", "catalogos", "movimientos", "presupuesto", "planeacion", "importacion")}, sort_keys=True)); print("archivos", sum(1 for p in Path(settings.MEDIA_ROOT).rglob("*") if p.is_file()))'
MSYS_NO_PATHCONV=1 docker compose exec -T web python manage.py shell -c "$CONTEO" > "$TMPDIR/conteo-real.txt"
MSYS_NO_PATHCONV=1 docker compose -p finanzas-prueba run --rm web python manage.py restaurar "$NOMBRE" --confirmar
MSYS_NO_PATHCONV=1 docker compose -p finanzas-prueba run --rm web python manage.py shell -c "$CONTEO" > "$TMPDIR/conteo-prueba.txt"
diff "$TMPDIR/conteo-real.txt" "$TMPDIR/conteo-prueba.txt" && echo IGUALES
docker compose -p finanzas-prueba down -v
```

Expected: `Restaurado: N registros y M archivos.` (sin «Respaldo de los datos anteriores», porque la instalación está vacía) y luego `IGUALES`. Si `diff` muestra diferencias, la tarea no está completa. (Usa como `$TMPDIR` la carpeta scratchpad de la sesión.)

- [ ] **Step 8: Suite completa y commit**

Run: `docker compose run --rm web pytest -q` y los dos `ruff`. Expected: verde.

```bash
git add scripts/respaldar.ps1 scripts/restaurar.ps1 scripts/programar_respaldo.ps1 README.md docs/ARQUITECTURA.md tests/test_uso_diario.py
git commit -m "feat(respaldo): scripts de respaldo diario y restauración para Windows (RNF-06)"
```

---

### Task 6: Importación del Excel — presupuesto y tasas de mercado

**Files:**
- Modify: `pyproject.toml` (dependencia `openpyxl>=3.1`), `uv.lock`
- Create: `apps/importacion/excel.py`
- Modify: `tests/conftest.py` (generador del Excel ficticio y fixture `excel_ficticio`)
- Test: `tests/importacion/test_imp_excel.py`

**Interfaces:**
- Consumes: `sembrar_catalogos`, `CATEGORIAS_INICIALES` (`apps.catalogos.servicios`); `normalizar` (`apps.importacion.clasificacion`); `obtener_plantilla` (`apps.presupuesto.servicios`).
- Produces (en `apps.importacion.excel`):
  - `class ErrorExcel(Exception)`: mensaje para el usuario.
  - `@dataclass class Resumen: creados: Counter; existentes: Counter; avisos: list[str]`
  - `SECCIONES: list[str]` = `["tasas de mercado", "ingresos de la plantilla", "conceptos", "gastos de la plantilla", "tarjetas", "créditos", "metas", "activos"]`
  - `importar_excel(ruta, hogar, aplicar=True) -> Resumen`: con `aplicar=False` todo se revierte al final.
  - Fixture `excel_ficticio(modificar=None) -> Path`: `modificar(libro)` cambia el libro de openpyxl antes de guardarlo.

- [ ] **Step 1: Dependencia**

En `pyproject.toml`, agregar `"openpyxl>=3.1",` al final de `dependencies`. Luego:

Run: `MSYS_NO_PATHCONV=1 docker run --rm -v "$(pwd -W):/app" -w /app ghcr.io/astral-sh/uv:python3.12-bookworm-slim uv lock` y `docker compose build web`
Expected: `uv.lock` incluye `openpyxl` y la imagen se construye.

- [ ] **Step 2: Generador del Excel ficticio**

En `tests/conftest.py`, agregar después de `RENGLONES_EXCEL`:

```python
# Encabezados de categoría del Excel: (texto, categoría, fila, columna del nombre).
BLOQUES_EXCEL = [
    ("🏡Casa", "Casa", 21, 3),
    ("🥑Comida", "Comida", 21, 9),
    ("❤️Familia", "Familia", 21, 15),
    ("🚓Transporte", "Transporte", 37, 3),
    ("✈️Viajes", "Viajes", 37, 9),
    ("🏦Deudas", "Deudas", 37, 15),
    ("🚑Salud", "Salud", 53, 3),
    ("📺Suscripciones", "Suscripciones", 53, 9),
    ("🏦Gastos anuales", "Gastos anuales", 53, 15),
    ("💅Cuidado personal", "Cuidado personal", 69, 3),
    ("📽️Entretenimiento", "Entretenimiento", 69, 9),
    ("🛸Otros", "Otros", 69, 15),
]


def _poner(hoja, fila, columna, *valores):
    for desplazamiento, valor in enumerate(valores):
        hoja.cell(fila, columna + desplazamiento, valor)


def _excel_ficticio(ruta, modificar=None):
    """Libro con el formato del «Financial Planner» y datos ficticios (montos de RENGLONES_EXCEL)."""
    from openpyxl import Workbook

    libro = Workbook()
    hoja = libro.active
    hoja.title = "Presupuesto"
    hoja["C2"] = "Ingresos Promedio Mensual"
    _poner(hoja, 3, 3, "Salario mensual (neto)", "Fijo", None, None, 32977.52)
    _poner(hoja, 4, 3, "Bono", "Variable", None, None, 0)
    _poner(hoja, 5, 3, "-", "-")
    hoja["C14"], hoja["G14"] = "¿Qué % de tus ingresos quieres ahorrar?", 0.05
    for encabezado, categoria, fila, columna in BLOQUES_EXCEL:
        _poner(hoja, fila, columna, encabezado, "¿Gasto Fijo?", "¿Pago con tarjeta?",
               "Gasto hormiga 🐜", "Monto mensual")  # fmt: skip
        renglones = RENGLONES_EXCEL.get(categoria, [])
        for numero, (monto, marcas) in enumerate(renglones, start=1):
            _poner(hoja, fila + numero, columna, f"{categoria} {numero}", "F" in marcas,
                   "T" in marcas, "H" in marcas, float(monto))  # fmt: skip
        _poner(hoja, fila + len(renglones) + 1, columna, "-", False, False, False, 0)

    deudas = libro.create_sheet("Deudas")
    deudas["C1"] = "Tarjetas de Crédito"
    _poner(deudas, 2, 3, "Banco", "Tarjeta", "Tasa promedio*", "Saldo Actual", "Línea de crédito")
    formula = "=IFERROR(AVERAGEIFS('No borrar'!$H$2:$H$190,'No borrar'!$F$2:$F$190,C4),0)"
    _poner(deudas, 3, 3, "Banco Demo", "Oro", 0.45, 6839.01, 7100, None, "No")
    _poner(deudas, 4, 3, "Banco Demo", "Clásica", formula, 1000, 5000, None, "Sí")
    _poner(deudas, 5, 3, "Otro", "Tarjeta", formula, 0, 0)
    deudas["C15"] = "Créditos"
    _poner(deudas, 16, 3, "Tipo de crédito", "Deuda inicial", "Deuda actual", "Mensualidad")
    _poner(deudas, 17, 3, "Préstamo auto", 41130, 38679.72, 1500)
    _poner(deudas, 18, 3, "-", 0, 0, 0)

    metas = libro.create_sheet("Metas de Ahorro")
    metas["C11"] = "¿Cuál es tu ahorro actual?"
    for columna, nombre, actual, meses, tasa, meta in [
        (3, "🎁Regalo", 0, 6, 0.10, 3000),
        (7, "🏖️Vacaciones", 2000, 12, 0.05, 20000),
        (11, "🚗Auto", 0, 12, 0.10, 0),
        (15, "🎲Otros", None, None, None, None),
    ]:
        metas.cell(8, columna, nombre)
        for fila, valor in zip((11, 12, 13, 14), (actual, meses, tasa, meta), strict=True):
            metas.cell(fila, columna + 2, valor)

    patrimonio = libro.create_sheet("Patrimonio")
    patrimonio["C2"] = "Activos"
    _poner(patrimonio, 3, 3, "Activo", None, "Nombre", None, "Valor actual")
    activos = [
        ("-", None, None),
        ("🏡Casa/Departamento", "Casa ejemplo", 1500000),
        ("🚗Auto", "Auto ejemplo", 150000),
        ("💰Cuentas de Ahorro", "-", 25000),
        ("-", "-", 0),
    ]
    for fila, (tipo, nombre, valor) in enumerate(activos, start=4):
        _poner(patrimonio, fila, 3, tipo, None, nombre, None, valor)

    tasas = libro.create_sheet("No borrar")
    _poner(tasas, 1, 6, "Banco", "Tarjeta", "Tasa")
    _poner(tasas, 2, 6, "Banco Demo", "Oro", 0.6904399999999999)
    _poner(tasas, 3, 6, "Banco Demo", "Clásica", 0.73228)

    if modificar:
        modificar(libro)
    libro.save(ruta)
    return ruta


@pytest.fixture
def excel_ficticio(tmp_path):
    def crear(modificar=None):
        return _excel_ficticio(tmp_path / "planner.xlsx", modificar)

    return crear
```

- [ ] **Step 3: Write the failing tests**

`tests/importacion/test_imp_excel.py` (completo):

```python
from decimal import Decimal as D

import pytest

from apps.catalogos.models import Categoria, Concepto, TasaMercado
from apps.catalogos.servicios import sembrar_catalogos
from apps.importacion.excel import ErrorExcel, importar_excel
from apps.presupuesto.models import Periodicidad, PlantillaGasto
from apps.presupuesto.servicios import obtener_plantilla, resumen_plantilla

pytestmark = pytest.mark.django_db


def test_plantilla_reproduce_los_valores_del_excel(excel_ficticio, hogar):
    importar_excel(excel_ficticio(), hogar)

    r = resumen_plantilla(obtener_plantilla(hogar))
    assert r.ingresos_totales == D("32977.52")
    assert r.gastos_totales == D("29235")
    assert r.gastos_fijos == D("26337")
    assert r.presupuesto_hormiga == D("2739")
    assert r.gasto_con_tarjeta == D("1298")
    assert r.meta_ahorro == D("1648.876")


def test_conceptos_en_su_categoria_sin_renglones_vacios(excel_ficticio, hogar):
    resumen = importar_excel(excel_ficticio(), hogar)

    assert resumen.creados["conceptos"] == 28
    assert resumen.creados["gastos de la plantilla"] == 28
    suscripcion = Concepto.objects.get(hogar=hogar, nombre="Suscripciones 1")
    assert suscripcion.categoria.nombre == "Suscripciones"
    assert suscripcion.es_hormiga
    assert not Concepto.objects.filter(hogar=hogar, nombre="-").exists()
    assert resumen.avisos == []


def test_ingresos_y_porcentaje_de_ahorro(excel_ficticio, hogar):
    importar_excel(excel_ficticio(), hogar)

    plantilla = obtener_plantilla(hogar)
    assert plantilla.porcentaje_ahorro == D("0.05")
    salario = plantilla.ingresos.get()  # el bono sin monto no se importa
    assert salario.nombre == "Salario mensual (neto)"
    assert salario.es_fijo
    assert salario.tipo_ingreso == "salario"


def test_concepto_sin_monto_no_entra_a_la_plantilla(excel_ficticio, hogar):
    def con_vuelos(libro):
        libro["Presupuesto"]["I38"] = "Vuelos"
        libro["Presupuesto"]["M38"] = 0

    importar_excel(excel_ficticio(con_vuelos), hogar)

    vuelos = Concepto.objects.get(hogar=hogar, nombre="Vuelos")
    assert vuelos.categoria.nombre == "Viajes"
    assert not PlantillaGasto.objects.filter(concepto=vuelos).exists()


def test_gastos_anuales_quedan_anuales(excel_ficticio, hogar):
    def con_predial(libro):
        libro["Presupuesto"]["O54"] = "Predial"
        libro["Presupuesto"]["S54"] = 1200

    importar_excel(excel_ficticio(con_predial), hogar)

    predial = PlantillaGasto.objects.get(concepto__nombre="Predial")
    assert predial.periodicidad == Periodicidad.ANUAL
    assert predial.monto_mensual() == D("100")


def test_tasas_de_mercado_con_promedio_de_las_repetidas(excel_ficticio, hogar):
    def repetida_y_sin_tasa(libro):
        hoja = libro["No borrar"]
        hoja["F4"], hoja["G4"], hoja["H4"] = "Banco Demo", "Oro", 0.5
        hoja["F5"], hoja["G5"], hoja["H5"] = "Banco Ejemplo", "Básica", "N/D"

    resumen = importar_excel(excel_ficticio(repetida_y_sin_tasa), hogar)

    assert resumen.creados["tasas de mercado"] == 2
    oro = TasaMercado.objects.get(institucion="Banco Demo", producto="Oro")
    assert oro.tasa_promedio == D("0.5952")  # (0.69044 + 0.5) / 2, como AVERAGEIFS
    assert TasaMercado.objects.get(producto="Clásica").tasa_promedio == D("0.7323")
    assert any("Tasas" in aviso for aviso in resumen.avisos)


def test_texto_en_lugar_de_monto(excel_ficticio, hogar):
    def con_texto(libro):
        libro["Presupuesto"]["G22"] = "mil pesos"  # monto de «Casa 1»

    resumen = importar_excel(excel_ficticio(con_texto), hogar)

    assert any("Casa 1" in a and "no es un número" in a for a in resumen.avisos)
    assert Concepto.objects.filter(hogar=hogar, nombre="Casa 1").exists()
    assert not PlantillaGasto.objects.filter(concepto__nombre="Casa 1").exists()


def test_importar_dos_veces_no_duplica(excel_ficticio, hogar):
    ruta = excel_ficticio()
    importar_excel(ruta, hogar)

    segundo = importar_excel(ruta, hogar)

    assert sum(segundo.creados.values()) == 0
    assert segundo.existentes["conceptos"] == 28
    assert PlantillaGasto.objects.filter(plantilla__hogar=hogar).count() == 28


def test_no_modifica_lo_capturado_a_mano(excel_ficticio, hogar):
    sembrar_catalogos(hogar)
    plantilla = obtener_plantilla(hogar)
    plantilla.porcentaje_ahorro = D("0.10")
    plantilla.save()
    casa = Concepto.objects.create(
        hogar=hogar, categoria=Categoria.objects.get(hogar=hogar, nombre="Casa"), nombre="casa 1"
    )
    PlantillaGasto.objects.create(hogar=hogar, plantilla=plantilla, concepto=casa, monto=D("999"))

    importar_excel(excel_ficticio(), hogar)

    plantilla.refresh_from_db()
    assert plantilla.porcentaje_ahorro == D("0.10")
    assert PlantillaGasto.objects.get(concepto=casa).monto == D("999")
    assert Concepto.objects.filter(hogar=hogar, nombre__iexact="casa 1").count() == 1


def test_simulacion_no_guarda_nada(excel_ficticio, hogar):
    resumen = importar_excel(excel_ficticio(), hogar, aplicar=False)

    assert resumen.creados["conceptos"] == 28
    assert not Concepto.objects.filter(hogar=hogar).exists()
    assert not TasaMercado.objects.exists()


def test_archivo_que_no_es_excel(tmp_path, hogar):
    ruta = tmp_path / "planner.xlsx"
    ruta.write_bytes(b"hola")

    with pytest.raises(ErrorExcel, match="No se pudo abrir"):
        importar_excel(ruta, hogar)


def test_hoja_faltante(excel_ficticio, hogar):
    def sin_metas(libro):
        del libro["Metas de Ahorro"]

    with pytest.raises(ErrorExcel, match="Metas de Ahorro"):
        importar_excel(excel_ficticio(sin_metas), hogar)
    assert not Concepto.objects.filter(hogar=hogar).exists()


def test_categorias_en_otro_orden(excel_ficticio, hogar):
    def movida(libro):
        libro["Presupuesto"]["C21"] = "🥑Comida"

    with pytest.raises(ErrorExcel, match="formato esperado"):
        importar_excel(excel_ficticio(movida), hogar)
    assert not Concepto.objects.filter(hogar=hogar).exists()
    assert not TasaMercado.objects.exists()
```

- [ ] **Step 4: Run tests to verify they fail**

Run: `docker compose run --rm web pytest tests/importacion/test_imp_excel.py -q`
Expected: error de colección `ModuleNotFoundError: No module named 'apps.importacion.excel'`.

- [ ] **Step 5: Implementación**

`apps/importacion/excel.py` (completo):

```python
"""Importación inicial desde el Excel «Financial Planner» (RF-ACC-02, RF-ACC-04).

Valida el formato completo antes de escribir y solo crea lo que falta: nunca modifica conceptos,
cuentas, metas, activos ni renglones que ya existen. La excepción es el catálogo global de tasas
de mercado, que se actualiza. Con aplicar=False, todo se revierte al final (simulación).
"""

import math
import re
import zipfile
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation

from django.db import transaction
from openpyxl import load_workbook
from openpyxl.utils import column_index_from_string
from openpyxl.utils.cell import coordinate_from_string
from openpyxl.utils.exceptions import InvalidFileException

from apps.catalogos.models import Categoria, Concepto, TasaMercado
from apps.catalogos.servicios import CATEGORIAS_INICIALES, sembrar_catalogos
from apps.importacion.clasificacion import normalizar
from apps.movimientos.models import TipoIngreso
from apps.presupuesto.models import Periodicidad, PlantillaGasto, PlantillaIngreso
from apps.presupuesto.servicios import obtener_plantilla

SECCIONES = [
    "tasas de mercado",
    "ingresos de la plantilla",
    "conceptos",
    "gastos de la plantilla",
    "tarjetas",
    "créditos",
    "metas",
    "activos",
]
HOJAS = ["Presupuesto", "Deudas", "Metas de Ahorro", "Patrimonio", "No borrar"]
# Celdas que identifican el formato de la plantilla: (hoja, celda, texto con el que empieza).
FORMATO = [
    ("Presupuesto", "C2", "Ingresos"),
    ("Presupuesto", "C14", "Que % de tus ingresos"),
    ("Deudas", "C1", "Tarjetas de credito"),
    ("Deudas", "C16", "Tipo de credito"),
    ("Metas de Ahorro", "C11", "Cual es tu ahorro actual"),
    ("Patrimonio", "C3", "Activo"),
    ("Patrimonio", "G3", "Valor actual"),
    ("No borrar", "F1", "Banco"),
    ("No borrar", "G1", "Tarjeta"),
    ("No borrar", "H1", "Tasa"),
]
# Presupuesto: encabezado de cada categoría (fila, columna del nombre), en el orden de
# CATEGORIAS_INICIALES. Cada bloque: 13 renglones con nombre, ¿fijo?, ¿tarjeta?, ¿hormiga?, monto.
BLOQUES = [(21, "C"), (21, "I"), (21, "O"), (37, "C"), (37, "I"), (37, "O"),
           (53, "C"), (53, "I"), (53, "O"), (69, "C"), (69, "I"), (69, "O")]  # fmt: skip
RENGLONES_POR_BLOQUE = 13
FILAS_INGRESOS = range(3, 11)
LIMITE = Decimal("1e10")
VACIOS = {"", "-"}
VERDADEROS = {"true", "verdadero", "si", "x"}


class ErrorExcel(Exception):
    """El archivo no es el Excel esperado; el mensaje es para el usuario."""


@dataclass
class Resumen:
    creados: Counter = field(default_factory=Counter)
    existentes: Counter = field(default_factory=Counter)
    avisos: list = field(default_factory=list)


def _columna(columna):
    return columna if isinstance(columna, int) else column_index_from_string(columna)


def _decimal(valor, decimales=2):
    """Número de la celda como Decimal, o None si no es un número utilizable."""
    if valor is None or isinstance(valor, bool):
        return None
    if isinstance(valor, int | float):
        if not math.isfinite(valor):
            return None
        texto = str(valor)
    elif isinstance(valor, str):
        texto = valor.replace("$", "").replace(",", "").strip()
    else:
        return None
    try:
        numero = Decimal(texto).quantize(Decimal(1).scaleb(-decimales))
    except InvalidOperation:
        return None
    if not numero.is_finite():  # «NaN» escrito como texto
        return None
    return numero if abs(numero) < LIMITE else None


def _sin_icono(texto):
    """«🏡Casa» → «Casa»: quita emojis y signos del inicio."""
    return re.sub(r"^\W+", "", texto).strip()


class Hoja:
    """Valores calculados de una hoja y, aparte, si una celda tiene fórmula."""

    def __init__(self, valores, formulas):
        self.valores = valores
        self.formulas = formulas

    def valor(self, fila, columna):
        return self.valores.cell(fila, _columna(columna)).value

    def texto(self, fila, columna):
        valor = self.valor(fila, columna)
        texto = " ".join(str(valor).split()) if valor is not None else ""
        return "" if texto in VACIOS else texto

    def numero(self, fila, columna, decimales=2):
        return _decimal(self.valor(fila, columna), decimales)

    def bandera(self, fila, columna):
        valor = self.valor(fila, columna)
        return valor is True or (isinstance(valor, str) and normalizar(valor) in VERDADEROS)

    def es_formula(self, fila, columna):
        valor = self.formulas.cell(fila, _columna(columna)).value
        return isinstance(valor, str) and valor.startswith("=")


def _abrir(ruta):
    try:
        valores = load_workbook(ruta, data_only=True)
        formulas = load_workbook(ruta, data_only=False)
    except (InvalidFileException, zipfile.BadZipFile, KeyError, OSError, ValueError) as error:
        raise ErrorExcel(
            "No se pudo abrir el archivo; debe ser el Excel (.xlsx) del planeador."
        ) from error
    faltantes = [nombre for nombre in HOJAS if nombre not in valores.sheetnames]
    if faltantes:
        raise ErrorExcel(f"Al Excel le falta la hoja «{faltantes[0]}».")
    return {nombre: Hoja(valores[nombre], formulas[nombre]) for nombre in HOJAS}


def _validar_formato(hojas):
    for nombre, celda, esperado in FORMATO:
        columna, fila = coordinate_from_string(celda)
        texto = normalizar(_sin_icono(hojas[nombre].texto(fila, columna)))
        if not texto.startswith(normalizar(esperado)):
            raise ErrorExcel(f"La hoja «{nombre}» no tiene el formato esperado (celda {celda}).")
    for (fila, columna), (categoria, _) in zip(BLOQUES, CATEGORIAS_INICIALES, strict=True):
        texto = normalizar(_sin_icono(hojas["Presupuesto"].texto(fila, columna)))
        if texto != normalizar(categoria):
            raise ErrorExcel(
                f"La hoja «Presupuesto» no tiene el formato esperado (celda {columna}{fila} "
                f"debería ser «{categoria}»)."
            )


@transaction.atomic
def importar_excel(ruta, hogar, aplicar=True):
    hojas = _abrir(ruta)
    _validar_formato(hojas)
    resumen = Resumen()
    sembrar_catalogos(hogar)
    _importar_tasas(hojas["No borrar"], resumen)
    _importar_presupuesto(hojas["Presupuesto"], hogar, resumen)
    if not aplicar:
        transaction.set_rollback(True)
    return resumen


def _importar_tasas(hoja, resumen):
    """Promedio por banco y tarjeta, como el AVERAGEIFS de la hoja Deudas del Excel."""
    tasas = defaultdict(list)
    for fila in range(2, hoja.valores.max_row + 1):
        institucion, producto = hoja.texto(fila, "F")[:80], hoja.texto(fila, "G")[:80]
        if not institucion and not producto:
            continue
        tasa = hoja.numero(fila, "H", decimales=6)
        if not institucion or not producto or tasa is None or not 0 <= tasa < 10:
            resumen.avisos.append(f"Tasas: el renglón {fila} no tiene banco, tarjeta o tasa válida.")
            continue
        tasas[(institucion, producto)].append(tasa)
    for (institucion, producto), valores in tasas.items():
        promedio = (sum(valores) / len(valores)).quantize(Decimal("0.0001"))
        _, nueva = TasaMercado.objects.update_or_create(
            institucion=institucion, producto=producto, defaults={"tasa_promedio": promedio}
        )
        (resumen.creados if nueva else resumen.existentes)["tasas de mercado"] += 1


def _monto(hoja, fila, columna, contexto, resumen):
    """Monto positivo de la celda; avisa si trae texto en lugar de un número."""
    valor = hoja.valor(fila, columna)
    monto = _decimal(valor)
    if monto is None and valor is not None and str(valor).strip() not in VACIOS:
        resumen.avisos.append(f"{contexto}: el monto «{valor}» no es un número; se omitió.")
    return monto if monto is not None and monto > 0 else None


def _importar_presupuesto(hoja, hogar, resumen):
    plantilla = obtener_plantilla(hogar)
    if not plantilla.ingresos.exists() and not plantilla.gastos.exists():
        porcentaje = hoja.numero(14, "G", decimales=4)
        if porcentaje is not None and 0 <= porcentaje <= 1:
            plantilla.porcentaje_ahorro = porcentaje
            plantilla.save(update_fields=["porcentaje_ahorro", "actualizado_en"])

    for fila in FILAS_INGRESOS:
        monto = _monto(hoja, fila, "G", f"Ingresos: renglón {fila}", resumen)
        if monto is None:
            continue
        nombre = (hoja.texto(fila, "C") or f"Ingreso {fila - 2}")[:80]
        if plantilla.ingresos.filter(nombre__iexact=nombre).exists():
            resumen.existentes["ingresos de la plantilla"] += 1
            continue
        PlantillaIngreso.objects.create(
            hogar=hogar,
            plantilla=plantilla,
            nombre=nombre,
            monto=monto,
            es_fijo=normalizar(hoja.texto(fila, "D")) != "variable",
            tipo_ingreso=(
                TipoIngreso.SALARIO if "salario" in normalizar(nombre) else TipoIngreso.OTRO
            ),
        )
        resumen.creados["ingresos de la plantilla"] += 1

    categorias = {c.nombre: c for c in Categoria.objects.del_hogar(hogar)}
    for (fila, columna), (nombre_categoria, _) in zip(BLOQUES, CATEGORIAS_INICIALES, strict=True):
        inicio = column_index_from_string(columna)
        vistos = set()
        for renglon in range(fila + 1, fila + 1 + RENGLONES_POR_BLOQUE):
            nombre = hoja.texto(renglon, inicio)[:80]
            if not nombre:
                continue
            if normalizar(nombre) in vistos:
                resumen.avisos.append(
                    f"{nombre_categoria}: «{nombre}» está repetido; se tomó el primero."
                )
                continue
            vistos.add(normalizar(nombre))
            es_fijo, con_tarjeta, es_hormiga = (
                hoja.bandera(renglon, inicio + desplazamiento) for desplazamiento in (1, 2, 3)
            )
            concepto = _concepto(
                hogar, categorias[nombre_categoria], nombre, es_fijo, es_hormiga, resumen
            )
            contexto = f"{nombre_categoria}: «{nombre}»"
            monto = _monto(hoja, renglon, inicio + 4, contexto, resumen)
            if monto is None:
                continue
            if PlantillaGasto.objects.filter(plantilla=plantilla, concepto=concepto).exists():
                resumen.existentes["gastos de la plantilla"] += 1
                continue
            PlantillaGasto.objects.create(
                hogar=hogar,
                plantilla=plantilla,
                concepto=concepto,
                monto=monto,
                es_fijo=es_fijo,
                con_tarjeta=con_tarjeta,
                es_hormiga=es_hormiga,
                periodicidad=(
                    Periodicidad.ANUAL
                    if nombre_categoria == "Gastos anuales"
                    else Periodicidad.MENSUAL
                ),
            )
            resumen.creados["gastos de la plantilla"] += 1


def _concepto(hogar, categoria, nombre, es_fijo, es_hormiga, resumen):
    existente = Concepto.objects.filter(
        hogar=hogar, categoria=categoria, nombre__iexact=nombre, domicilio=None
    ).first()
    if existente:
        resumen.existentes["conceptos"] += 1
        return existente
    resumen.creados["conceptos"] += 1
    return Concepto.objects.create(
        hogar=hogar, categoria=categoria, nombre=nombre, es_fijo=es_fijo, es_hormiga=es_hormiga
    )
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `docker compose run --rm web pytest tests/importacion/test_imp_excel.py -q`
Expected: 13 passed.

- [ ] **Step 7: Suite completa y commit**

Run: `docker compose run --rm web pytest -q` y los dos `ruff`. Expected: verde.

```bash
git add pyproject.toml uv.lock apps/importacion/excel.py tests/conftest.py tests/importacion/test_imp_excel.py
git commit -m "feat(importacion): importar presupuesto, conceptos y tasas de mercado desde el Excel (RF-ACC-02, RF-ACC-04)"
```

---

### Task 7: Importación del Excel — deudas, metas, activos y comando

**Files:**
- Modify: `apps/importacion/excel.py`
- Create: `apps/importacion/management/__init__.py`, `apps/importacion/management/commands/__init__.py` (vacíos)
- Create: `apps/importacion/management/commands/importar_excel.py`
- Create: `scripts/importar_excel.ps1`
- Modify: `README.md`, `docs/DEF.md` (nota en RF-ACC-02)
- Test: `tests/importacion/test_imp_excel_planeacion.py`

**Interfaces:**
- Consumes: `importar_excel`, `Resumen`, `SECCIONES`, `ErrorExcel`, `Hoja`, `_decimal`, `_sin_icono` (tarea 6); `tasa_sugerida` (`apps.catalogos.servicios`); `MESES_MAXIMOS` (`apps.planeacion.models`).
- Produces: comando `importar_excel ARCHIVO [--email EMAIL] [--aplicar] [--detalle]`; script `scripts/importar_excel.ps1 -Archivo RUTA [-Email EMAIL] [-Aplicar]`.

- [ ] **Step 1: Write the failing tests**

`tests/importacion/test_imp_excel_planeacion.py` (completo):

```python
import re
from decimal import Decimal as D

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.catalogos.models import Concepto, Cuenta
from apps.catalogos.servicios import tasa_sugerida
from apps.importacion.excel import importar_excel
from apps.planeacion.models import Activo, MetaAhorro

pytestmark = pytest.mark.django_db


def test_tarjetas_con_tasa_capturada_o_de_mercado(excel_ficticio, hogar):
    importar_excel(excel_ficticio(), hogar)

    oro = Cuenta.objects.get(hogar=hogar, nombre="Banco Demo Oro")
    assert oro.tipo == Cuenta.Tipo.CREDITO
    assert (oro.institucion, oro.producto) == ("Banco Demo", "Oro")
    assert oro.saldo_actual == D("6839.01")
    assert oro.linea_credito == D("7100")
    assert oro.tasa_anual == D("0.45")
    assert oro.paga_total_mensual is False
    clasica = Cuenta.objects.get(hogar=hogar, nombre="Banco Demo Clásica")
    assert clasica.tasa_anual is None  # en el Excel era el promedio de mercado (fórmula)
    assert tasa_sugerida(clasica) == D("0.7323")
    assert clasica.paga_total_mensual is True
    assert not Cuenta.objects.filter(hogar=hogar, institucion="Otro").exists()


def test_creditos(excel_ficticio, hogar):
    resumen = importar_excel(excel_ficticio(), hogar)

    auto = Cuenta.objects.get(hogar=hogar, nombre="Préstamo auto")
    assert auto.tipo == Cuenta.Tipo.PRESTAMO
    assert auto.monto_inicial == D("41130")
    assert auto.saldo_actual == D("38679.72")
    assert auto.mensualidad == D("1500")
    assert resumen.creados["créditos"] == 1
    assert resumen.creados["tarjetas"] == 2


def test_metas_con_monto(excel_ficticio, hogar):
    importar_excel(excel_ficticio(), hogar)

    regalo = MetaAhorro.objects.get(hogar=hogar, nombre="Regalo")
    assert regalo.tipo == MetaAhorro.Tipo.REGALO
    assert regalo.monto_objetivo == D("3000")
    assert regalo.ahorro_actual == D("0")
    assert regalo.meses == 6
    assert regalo.tasa_anual == D("0.1000")
    vacaciones = MetaAhorro.objects.get(hogar=hogar, nombre="Vacaciones")
    assert vacaciones.tipo == MetaAhorro.Tipo.VACACIONES
    assert vacaciones.ahorro_actual == D("2000")
    assert MetaAhorro.objects.filter(hogar=hogar).count() == 2


def test_meta_con_meses_invalidos_usa_12_y_avisa(excel_ficticio, hogar):
    def meses_raros(libro):
        libro["Metas de Ahorro"]["E12"] = "medio año"

    resumen = importar_excel(excel_ficticio(meses_raros), hogar)

    assert MetaAhorro.objects.get(hogar=hogar, nombre="Regalo").meses == 12
    assert any("Regalo" in aviso for aviso in resumen.avisos)


def test_activos(excel_ficticio, hogar):
    importar_excel(excel_ficticio(), hogar)

    casa = Activo.objects.get(hogar=hogar, nombre="Casa ejemplo")
    assert casa.tipo == Activo.Tipo.INMUEBLE
    assert casa.valor_actual == D("1500000")
    ahorro = Activo.objects.get(hogar=hogar, nombre="Cuentas de Ahorro")
    assert ahorro.tipo == Activo.Tipo.CUENTA_AHORRO
    assert Activo.objects.filter(hogar=hogar).count() == 3


def test_segunda_importacion_no_duplica_ni_sobrescribe(excel_ficticio, hogar):
    ruta = excel_ficticio()
    importar_excel(ruta, hogar)
    Cuenta.objects.filter(hogar=hogar, nombre="Banco Demo Oro").update(saldo_actual=D("1"))

    segundo = importar_excel(ruta, hogar)

    assert sum(segundo.creados.values()) == 0
    assert segundo.existentes["tarjetas"] == 2
    assert segundo.existentes["metas"] == 2
    assert segundo.existentes["activos"] == 3
    assert Cuenta.objects.get(hogar=hogar, nombre="Banco Demo Oro").saldo_actual == D("1")


def test_comando_simula_por_omision(excel_ficticio, hogar, capsys):
    call_command("importar_excel", str(excel_ficticio()))

    salida = capsys.readouterr().out
    assert "Simulación" in salida
    assert re.search(r"^conceptos\s+28\s+0$", salida, re.MULTILINE)
    assert "Avisos: 0" in salida
    assert not Concepto.objects.filter(hogar=hogar).exists()


def test_comando_aplicar(excel_ficticio, hogar, usuario):
    call_command("importar_excel", str(excel_ficticio()), email=usuario.email, aplicar=True)

    assert Concepto.objects.filter(hogar=hogar).count() == 28
    assert Activo.objects.filter(hogar=hogar).count() == 3


def test_comando_no_muestra_nombres_sin_detalle(excel_ficticio, hogar, capsys):
    def con_texto(libro):
        libro["Presupuesto"]["G22"] = "mil pesos"

    ruta = str(excel_ficticio(con_texto))
    call_command("importar_excel", ruta)
    sin_detalle = capsys.readouterr().out
    call_command("importar_excel", ruta, detalle=True)
    con_detalle = capsys.readouterr().out

    assert "Avisos: 1 (usa --detalle para verlos)" in sin_detalle
    assert "Casa 1" not in sin_detalle
    assert "Casa 1" in con_detalle


def test_comando_con_email_sin_hogar(excel_ficticio, hogar):
    with pytest.raises(CommandError, match="No hay un hogar"):
        call_command("importar_excel", str(excel_ficticio()), email="nadie@example.com")


def test_comando_con_archivo_invalido(tmp_path, hogar):
    ruta = tmp_path / "planner.xlsx"
    ruta.write_bytes(b"hola")

    with pytest.raises(CommandError, match="No se pudo abrir"):
        call_command("importar_excel", str(ruta))
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `docker compose run --rm web pytest tests/importacion/test_imp_excel_planeacion.py -q`
Expected: 11 failed (no se crean cuentas, metas ni activos; `Unknown command: 'importar_excel'`).

- [ ] **Step 3: Deudas, metas y activos**

En `apps/importacion/excel.py`:

Reemplazar las importaciones de modelos por:

```python
from apps.catalogos.models import Categoria, Concepto, Cuenta, TasaMercado
from apps.catalogos.servicios import CATEGORIAS_INICIALES, sembrar_catalogos
from apps.importacion.clasificacion import normalizar
from apps.movimientos.models import TipoIngreso
from apps.planeacion.models import MESES_MAXIMOS, Activo, MetaAhorro
from apps.presupuesto.models import Periodicidad, PlantillaGasto, PlantillaIngreso
from apps.presupuesto.servicios import obtener_plantilla
```

Agregar después de `VERDADEROS`:

```python
FILAS_TARJETAS = range(3, 9)
FILAS_CREDITOS = range(17, 25)
FILAS_ACTIVOS = range(4, 15)
# Metas: columna del nombre (fila 8); los valores van dos columnas a la derecha, filas 11–14.
COLUMNAS_METAS = ["C", "G", "K", "O"]
TIPOS_META = {
    "regalo": MetaAhorro.Tipo.REGALO,
    "vacaciones": MetaAhorro.Tipo.VACACIONES,
    "auto": MetaAhorro.Tipo.AUTO,
    "casa": MetaAhorro.Tipo.CASA,
    "educacion": MetaAhorro.Tipo.EDUCACION,
    "fondo para emergencias": MetaAhorro.Tipo.FONDO_EMERGENCIA,
    "compra importante": MetaAhorro.Tipo.COMPRA_IMPORTANTE,
    "remodelacion": MetaAhorro.Tipo.REMODELACION,
}
TIPOS_ACTIVO = {
    "casa/departamento": Activo.Tipo.INMUEBLE,
    "auto": Activo.Tipo.AUTO,
    "cuentas de ahorro": Activo.Tipo.CUENTA_AHORRO,
    "cuentas de inversion": Activo.Tipo.CUENTA_INVERSION,
    "acciones": Activo.Tipo.ACCIONES,
    "stock options": Activo.Tipo.STOCK_OPTIONS,
    "afore": Activo.Tipo.AFORE,
    "terreno": Activo.Tipo.TERRENO,
}
```

En `importar_excel`, reemplazar la línea `_importar_presupuesto(hojas["Presupuesto"], hogar, resumen)` por:

```python
    _importar_presupuesto(hojas["Presupuesto"], hogar, resumen)
    _importar_deudas(hojas["Deudas"], hogar, resumen)
    _importar_metas(hojas["Metas de Ahorro"], hogar, resumen)
    _importar_activos(hojas["Patrimonio"], hogar, resumen)
```

Agregar al final del archivo:

```python
def _crear_cuenta(hogar, resumen, seccion, nombre, **campos):
    if Cuenta.objects.filter(hogar=hogar, nombre__iexact=nombre).exists():
        resumen.existentes[seccion] += 1
        return
    Cuenta.objects.create(hogar=hogar, nombre=nombre, **campos)
    resumen.creados[seccion] += 1


def _importar_deudas(hoja, hogar, resumen):
    for fila in FILAS_TARJETAS:
        banco, producto = hoja.texto(fila, "C")[:80], hoja.texto(fila, "D")[:80]
        saldo, linea = hoja.numero(fila, "F"), hoja.numero(fila, "G")
        if not banco or not (saldo or linea):
            continue  # renglón vacío o de ejemplo de la plantilla
        if not producto or normalizar(producto).startswith(normalizar(banco)):
            nombre = producto or banco
        else:
            nombre = f"{banco} {producto}"
        # Con fórmula, el Excel usaba el promedio de mercado: la app lo calcula (tasa_sugerida).
        tasa = None if hoja.es_formula(fila, "E") else hoja.numero(fila, "E", decimales=4)
        _crear_cuenta(
            hogar,
            resumen,
            "tarjetas",
            nombre[:80],
            tipo=Cuenta.Tipo.CREDITO,
            institucion=banco,
            producto=producto,
            saldo_actual=saldo or Decimal("0"),
            linea_credito=linea,
            tasa_anual=tasa if tasa is not None and 0 < tasa < 10 else None,
            paga_total_mensual={"si": True, "no": False}.get(normalizar(hoja.texto(fila, "I"))),
        )
    for fila in FILAS_CREDITOS:
        nombre = hoja.texto(fila, "C")[:80]
        inicial, actual, mensualidad = (hoja.numero(fila, columna) for columna in "DEF")
        if not nombre or not (inicial or actual or mensualidad):
            continue
        _crear_cuenta(
            hogar,
            resumen,
            "créditos",
            nombre,
            tipo=Cuenta.Tipo.PRESTAMO,
            monto_inicial=inicial,
            saldo_actual=actual or Decimal("0"),
            mensualidad=mensualidad,
        )


def _importar_metas(hoja, hogar, resumen):
    for columna in COLUMNAS_METAS:
        inicio = column_index_from_string(columna)
        nombre = _sin_icono(hoja.texto(8, inicio))[:80] or "Meta"
        meta = hoja.numero(14, inicio + 2)
        if meta is None or meta <= 0:
            continue
        if MetaAhorro.objects.filter(hogar=hogar, nombre__iexact=nombre).exists():
            resumen.existentes["metas"] += 1
            continue
        meses = hoja.numero(12, inicio + 2, decimales=0)
        if meses is None or not 1 <= meses <= MESES_MAXIMOS:
            resumen.avisos.append(f"Metas: «{nombre}» no tiene meses válidos; se usaron 12.")
            meses = Decimal("12")
        tasa = hoja.numero(13, inicio + 2, decimales=4)
        MetaAhorro.objects.create(
            hogar=hogar,
            nombre=nombre,
            tipo=TIPOS_META.get(normalizar(nombre), MetaAhorro.Tipo.OTRO),
            monto_objetivo=meta,
            ahorro_actual=max(hoja.numero(11, inicio + 2) or Decimal("0"), Decimal("0")),
            meses=int(meses),
            tasa_anual=tasa if tasa is not None and 0 <= tasa < 10 else Decimal("0"),
        )
        resumen.creados["metas"] += 1


def _importar_activos(hoja, hogar, resumen):
    for fila in FILAS_ACTIVOS:
        valor = hoja.numero(fila, "G")
        if valor is None or valor <= 0:
            continue
        tipo = _sin_icono(hoja.texto(fila, "C"))
        nombre = (hoja.texto(fila, "E") or tipo or "Activo")[:120]
        if Activo.objects.filter(hogar=hogar, nombre__iexact=nombre).exists():
            resumen.existentes["activos"] += 1
            continue
        Activo.objects.create(
            hogar=hogar,
            nombre=nombre,
            valor_actual=valor,
            tipo=TIPOS_ACTIVO.get(normalizar(tipo), Activo.Tipo.OTRO),
        )
        resumen.creados["activos"] += 1
```

- [ ] **Step 4: Comando**

`apps/importacion/management/commands/importar_excel.py` (completo):

```python
from django.core.management.base import BaseCommand, CommandError

from apps.core.models import Membresia
from apps.importacion.excel import SECCIONES, ErrorExcel, importar_excel


class Command(BaseCommand):
    help = (
        "Importación inicial desde el Excel del planeador (RF-ACC-04). "
        "Por omisión solo simula; usa --aplicar para guardar."
    )

    def add_arguments(self, parser):
        parser.add_argument("archivo", help="Ruta del .xlsx dentro del contenedor.")
        parser.add_argument("--email", help="Email del dueño del hogar (si hay más de uno).")
        parser.add_argument("--aplicar", action="store_true", help="Guarda los datos.")
        parser.add_argument(
            "--detalle", action="store_true", help="Muestra los avisos (pueden incluir nombres)."
        )

    def handle(self, *args, archivo, email=None, aplicar=False, detalle=False, **opciones):
        hogar = self._hogar(email)
        try:
            resumen = importar_excel(archivo, hogar, aplicar=aplicar)
        except ErrorExcel as error:
            raise CommandError(str(error)) from error
        if not aplicar:
            self.stdout.write(
                self.style.WARNING("Simulación: no se guardó nada. Usa --aplicar para importar.")
            )
        self.stdout.write(f"{'Sección':<26}{'nuevos':>8}{'ya existían':>13}")
        for seccion in SECCIONES:
            creados, existentes = resumen.creados[seccion], resumen.existentes[seccion]
            self.stdout.write(f"{seccion:<26}{creados:>8}{existentes:>13}")
        pista = " (usa --detalle para verlos)" if resumen.avisos and not detalle else ""
        self.stdout.write(f"Avisos: {len(resumen.avisos)}{pista}")
        if detalle:
            for aviso in resumen.avisos:
                self.stdout.write(f"- {aviso}")

    def _hogar(self, email):
        membresias = Membresia.objects.select_related("hogar").order_by("creado_en", "id")
        if email:
            membresia = membresias.filter(usuario__email__iexact=email).first()
            if membresia is None:
                raise CommandError(f"No hay un hogar para {email}.")
            return membresia.hogar
        hogares = {membresia.hogar_id: membresia.hogar for membresia in membresias}
        if len(hogares) != 1:
            raise CommandError("Indica --email: hay más de un hogar, o ninguno.")
        return next(iter(hogares.values()))
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `docker compose run --rm web pytest tests/importacion/test_imp_excel_planeacion.py tests/importacion/test_imp_excel.py -q`
Expected: 24 passed.

- [ ] **Step 6: Script, README y DEF**

`scripts/importar_excel.ps1` (completo):

```powershell
# Importación inicial desde el Excel del planeador (RF-ACC-04). Por omisión solo simula.
# Uso: powershell -ExecutionPolicy Bypass -File scripts\importar_excel.ps1 -Archivo "..\2026\documentos\Financial Planner template.xlsx" [-Email tu@email.com] [-Aplicar]
param(
    [Parameter(Mandatory = $true)][string]$Archivo,
    [string]$Email,
    [switch]$Aplicar
)
$ruta = (Resolve-Path $Archivo).Path
$raiz = Split-Path -Parent $PSScriptRoot
Set-Location $raiz
$destino = "/tmp/planner.xlsx"
docker compose cp "$ruta" "web:$destino"
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
$argumentos = @("compose", "exec", "-T", "web", "python", "manage.py", "importar_excel", $destino)
if ($Email) { $argumentos += @("--email", $Email) }
if ($Aplicar) { $argumentos += "--aplicar" }
try {
    & docker @argumentos
    $codigo = $LASTEXITCODE
}
finally {
    docker compose exec -T web rm -f $destino
}
exit $codigo
```

Agregar a `README.md` después de «## Primer uso»:

````markdown
### Cargar tu Excel (una sola vez)

Trae tu presupuesto, conceptos, tarjetas, créditos, metas, activos y el catálogo de tasas de mercado del «Financial Planner». Solo crea lo que falta: no duplica ni cambia lo que ya capturaste.

```powershell
# 1) Simulación: muestra cuántos registros se crearían, sin guardar nada.
powershell -ExecutionPolicy Bypass -File scripts\importar_excel.ps1 -Archivo "..\2026\documentos\Financial Planner template.xlsx"
# 2) Si los números se ven bien, importa de verdad.
powershell -ExecutionPolicy Bypass -File scripts\importar_excel.ps1 -Archivo "..\2026\documentos\Financial Planner template.xlsx" -Aplicar
```

Si aparecen avisos (montos con texto, renglones repetidos), agrega `--detalle` al comando `importar_excel` para verlos. El archivo se copia al contenedor solo mientras se importa.
````

En `docs/DEF.md`, al final de la fila de RF-ACC-02 (antes de `| M |`), agregar: ` *(Los conceptos y el catálogo de tasas se cargan con la importación del Excel, RF-ACC-04: no se guardan datos de la plantilla en el repositorio.)*`

- [ ] **Step 7: Simulación con el Excel real (solo conteos)**

Primero, un conteo independiente del Excel real, hecho fuera de la app y que solo imprime números. Guarda este script en la carpeta scratchpad (no en el repo) como `contar_excel.py`:

```python
import sys

import openpyxl

ruta = sys.argv[1]
libro = openpyxl.load_workbook(ruta, data_only=True)
p, d, m, a, t = (libro[h] for h in ("Presupuesto", "Deudas", "Metas de Ahorro", "Patrimonio", "No borrar"))


def texto(v):
    s = " ".join(str(v).split()) if v is not None else ""
    return "" if s in ("", "-") else s


def num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and v > 0


conceptos = gastos = 0
for fila in (21, 37, 53, 69):
    for col in (3, 9, 15):
        vistos = set()
        for r in range(fila + 1, fila + 14):
            n = texto(p.cell(r, col).value).lower()
            if n and n not in vistos:
                vistos.add(n)
                conceptos += 1
                gastos += num(p.cell(r, col + 4).value)
tasas = {(texto(t.cell(r, 6).value), texto(t.cell(r, 7).value)) for r in range(2, t.max_row + 1)
         if texto(t.cell(r, 6).value) and texto(t.cell(r, 7).value) and num(t.cell(r, 8).value)}
print("tasas", len(tasas))
print("ingresos", sum(num(p.cell(r, 7).value) for r in range(3, 11)))
print("conceptos", conceptos, "gastos", gastos)
print("tarjetas", sum(1 for r in range(3, 9) if texto(d.cell(r, 3).value) and (num(d.cell(r, 6).value) or num(d.cell(r, 7).value))))
print("creditos", sum(1 for r in range(17, 25) if texto(d.cell(r, 3).value) and any(num(d.cell(r, c).value) for c in (4, 5, 6))))
print("metas", sum(1 for c in (5, 9, 13, 17) if num(m.cell(14, c).value)))
print("activos", sum(1 for r in range(4, 15) if num(a.cell(r, 7).value)))
```

Run: `docker compose cp "../2026/documentos/Financial Planner template.xlsx" web:/tmp/planner.xlsx`, `docker compose cp <scratchpad>/contar_excel.py web:/tmp/contar_excel.py`, `docker compose exec -T web python /tmp/contar_excel.py /tmp/planner.xlsx`, `docker compose exec -T web rm -f /tmp/contar_excel.py /tmp/planner.xlsx`.

Run (PowerShell, simulación con el script): `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\importar_excel.ps1 -Archivo "..\2026\documentos\Financial Planner template.xlsx"`
Expected: «Simulación: no se guardó nada…»; los «nuevos» de cada sección coinciden con el conteo independiente (con la base vacía, nada «ya existía»; `gastos de la plantilla` = `gastos`). No uses `--detalle`, porque mostraría nombres reales. Si no coinciden, investiga con `superpowers:systematic-debugging` antes de seguir.

**Detenerse aquí:** la importación real (`-Aplicar`) escribe en la base de datos del usuario. Pídele autorización o deja que la corra él con las instrucciones del README.

- [ ] **Step 8: Suite completa y commit**

Run: `docker compose run --rm web pytest -q`, los dos `ruff` y `sh tests/verificar_imagen.sh`. Expected: verde y «OK: ningún archivo sensible entró a la imagen».

```bash
git add apps/importacion/excel.py apps/importacion/management scripts/importar_excel.ps1 README.md docs/DEF.md tests/importacion/test_imp_excel_planeacion.py
git commit -m "feat(importacion): importar tarjetas, créditos, metas y activos del Excel, con comando y script (RF-ACC-04)"
```
