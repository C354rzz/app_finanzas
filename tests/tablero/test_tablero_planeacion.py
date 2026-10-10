from datetime import date
from decimal import Decimal as D

import pytest

from apps.calculos.comun import redondear
from apps.planeacion.models import Activo, MetaAhorro
from apps.tablero.servicios import armar_tablero

pytestmark = pytest.mark.django_db


def metas_del_excel(hogar):
    for nombre, monto in [("Regalo", "20000"), ("Vacaciones", "45000")]:
        MetaAhorro.objects.create(
            hogar=hogar, nombre=nombre, monto_objetivo=D(monto), fecha_inicio=date(2026, 10, 1)
        )


def mensajes(tablero):
    return " | ".join(alerta.mensaje for alerta in tablero.alertas)


def test_tablero_incluye_metas_y_alerta_si_no_alcanzan(plantilla_excel, hogar):
    metas_del_excel(hogar)

    t = armar_tablero(hogar, 2026, 10)

    assert redondear(t.metas.total_mensual) == D("5172.87")
    assert "Tus metas de ahorro piden $5,172.87 al mes" in mensajes(t)
    assert "$3,742.52" in mensajes(t)


def test_sin_metas_no_hay_alerta(plantilla_excel, hogar):
    t = armar_tablero(hogar, 2026, 10)

    assert t.metas.filas == []
    assert "metas de ahorro piden" not in mensajes(t)


def test_con_filtro_no_se_muestran_metas(plantilla_excel, catalogo, hogar):
    metas_del_excel(hogar)

    t = armar_tablero(hogar, 2026, 10, domicilio=catalogo.fidel)

    assert t.metas is None
    assert "metas de ahorro piden" not in mensajes(t)


def test_tablero_incluye_patrimonio(catalogo, hogar):
    Activo.objects.create(hogar=hogar, nombre="Auto", valor_actual=D("100000"))

    assert armar_tablero(hogar, 2026, 10).patrimonio.neto == D("54481.27")


def test_pantalla_del_tablero_con_metas_y_patrimonio(cliente, plantilla_excel, hogar):
    metas_del_excel(hogar)

    contenido = cliente.get("/tablero/2026/10/").content.decode()

    assert "Necesitas ahorrar" in contenido
    assert "$5,172.87" in contenido
    assert "Patrimonio neto" in contenido


def test_pantalla_del_tablero_sin_metas(cliente):
    contenido = cliente.get("/tablero/2026/10/").content.decode()

    assert "Aún no tienes metas de ahorro." in contenido
