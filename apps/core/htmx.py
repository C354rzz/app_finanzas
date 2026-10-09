"""Ayudas para vistas que responden a HTMX."""

from django.http import HttpResponse
from django.shortcuts import render

EVENTO_DATOS = "datosActualizados"


def es_htmx(request):
    return request.headers.get("HX-Request") == "true"


def datos_actualizados():
    """204 + evento: el navegador cierra el modal y recarga la vista (static/js/app.js)."""
    respuesta = HttpResponse(status=204)
    respuesta["HX-Trigger"] = EVENTO_DATOS
    return respuesta


def responder_formulario(request, contexto):
    """Formulario dentro del modal (HTMX) o como página completa (sin JavaScript)."""
    plantilla = (
        "componentes/_formulario_modal.html"
        if es_htmx(request)
        else "componentes/pagina_formulario.html"
    )
    return render(request, plantilla, contexto)
