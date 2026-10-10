"""Regresiones de la revisión final del plan 3."""

import pytest

from apps.planeacion.models import MetaAhorro

pytestmark = pytest.mark.django_db
HTMX = {"HX-Request": "true"}


def test_meta_con_fecha_de_inicio_muy_lejana_es_error(cliente):
    datos = {
        "tipo": "regalo",
        "nombre": "Lejana",
        "monto_objetivo": "1000",
        "ahorro_actual": "0",
        "meses": "600",
        "tasa_anual": "10",
        "fecha_inicio": "9990-01-01",
        "activa": "on",
    }

    respuesta = cliente.post("/planeacion/metas/nueva/", datos, headers=HTMX)

    assert "fecha_inicio" in respuesta.context["formulario"].errors
    assert not MetaAhorro.objects.exists()
    assert cliente.get("/").status_code == 302


def test_mes_de_pago_anticipado_enorme_es_error_y_no_500(cliente):
    datos = {
        "monto": "30000",
        "tasa_anual": "25",
        "meses": "12",
        "pagos_anticipados": "9" * 4301 + "=5",
    }

    respuesta = cliente.get("/planeacion/simulador/", datos)

    assert respuesta.status_code == 200
    assert "No entiendo" in str(respuesta.context["formulario"].errors["pagos_anticipados"])
