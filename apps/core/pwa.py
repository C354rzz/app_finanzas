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
