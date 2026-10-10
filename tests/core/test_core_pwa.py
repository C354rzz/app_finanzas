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
