from decimal import Decimal as D

from apps.core.htmx import EVENTO_DATOS, datos_actualizados, es_htmx
from apps.core.templatetags.formato import ancho_barra, dinero, porcentaje


def test_dinero_con_separador_de_miles_y_centavos():
    assert dinero(D("32977.52")) == "$32,977.52"
    assert dinero(D("1648.876")) == "$1,648.88"
    assert dinero(D("0")) == "$0.00"


def test_dinero_negativo_y_vacio():
    assert dinero(D("-3742.5")) == "-$3,742.50"
    assert dinero(D("-0.001")) == "$0.00"
    assert dinero(None) == "—"


def test_porcentaje_de_una_fraccion():
    assert porcentaje(D("0.963226")) == "96.32%"
    assert porcentaje(D("0.05"), 0) == "5%"
    assert porcentaje(None) == "—"


def test_ancho_de_barra_entre_0_y_100():
    assert ancho_barra(D("0.5")) == 50
    assert ancho_barra(D("1.7")) == 100
    assert ancho_barra(D("-0.2")) == 0
    assert ancho_barra(None) == 0


def test_respuesta_de_datos_actualizados(rf):
    respuesta = datos_actualizados()

    assert respuesta.status_code == 204
    assert respuesta["HX-Trigger"] == EVENTO_DATOS
    assert es_htmx(rf.get("/", headers={"HX-Request": "true"}))
    assert not es_htmx(rf.get("/"))
