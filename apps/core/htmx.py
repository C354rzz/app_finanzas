"""Ayudas para vistas que responden a HTMX."""

from django.http import HttpResponse

EVENTO_DATOS = "datosActualizados"


def es_htmx(request):
    return request.headers.get("HX-Request") == "true"


def datos_actualizados():
    """204 + evento: el navegador cierra el modal y recarga la vista (static/js/app.js)."""
    respuesta = HttpResponse(status=204)
    respuesta["HX-Trigger"] = EVENTO_DATOS
    return respuesta
