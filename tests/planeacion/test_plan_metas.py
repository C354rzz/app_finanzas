from datetime import date
from decimal import Decimal as D

import pytest

from apps.calculos.comun import redondear
from apps.calculos.presupuesto import LineaGasto, LineaIngreso, resumir_presupuesto
from apps.planeacion.mensajes import mensaje_metas, mensaje_tarjeta, mensaje_uso
from apps.planeacion.models import MetaAhorro
from apps.planeacion.servicios import resumir_metas
from apps.presupuesto.mensajes import ALERTA, BIEN, CUIDADO
from apps.presupuesto.servicios import resumen_plantilla

pytestmark = pytest.mark.django_db


def resumen(ingresos, gastos):
    return resumir_presupuesto(
        [LineaIngreso(monto=D(ingresos))], [LineaGasto(monto=D(gastos))], D("0.05")
    )


def metas_del_excel(hogar):
    for nombre, monto in [("Regalo", "20000"), ("Vacaciones", "45000")]:
        MetaAhorro.objects.create(
            hogar=hogar,
            nombre=nombre,
            monto_objetivo=D(monto),
            fecha_inicio=date(2026, 10, 1),
        )


def test_metas_del_excel(plantilla_excel, hogar):
    metas_del_excel(hogar)

    r = resumir_metas(hogar, resumen_plantilla(plantilla_excel))

    assert [redondear(f.aporte) for f in r.filas] == [D("1591.65"), D("3581.21")]
    assert redondear(r.total_mensual) == D("5172.87")
    assert redondear(r.porcentaje_ingresos, 4) == D("0.1569")
    assert r.nivel == CUIDADO
    assert r.filas[0].fecha_fin == date(2027, 10, 1)


def test_metas_inactivas_y_de_otro_hogar_no_cuentan(hogar, otro_hogar):
    metas_del_excel(hogar)
    MetaAhorro.objects.filter(nombre="Vacaciones").update(activa=False)
    MetaAhorro.objects.create(hogar=otro_hogar, nombre="Ajena", monto_objetivo=D("99999"))

    r = resumir_metas(hogar, resumen("32977.52", "29235"))

    assert [f.meta.nombre for f in r.filas] == ["Regalo"]


def test_sin_metas_ni_ingresos(hogar):
    r = resumir_metas(hogar, resumen("0", "0"))

    assert (r.filas, r.total_mensual, r.porcentaje_ingresos) == ([], 0, None)


def test_mensajes_de_metas():
    assert mensaje_metas(D("6000"), D("5172.87"))[0] == BIEN
    assert mensaje_metas(D("5172.87"), D("5172.87"))[0] == CUIDADO
    assert mensaje_metas(D("-1"), D("0"))[0] == ALERTA
    assert mensaje_metas(D("-1"), D("0"))[1].startswith("⛔ ¡Tus gastos son mayores")


def test_mensajes_de_tarjetas():
    assert mensaje_uso("bueno").startswith("👏¡Buen nivel")
    assert mensaje_uso("cuidado").startswith("⚠️ Cuidado con el uso")
    assert (
        mensaje_uso("riesgo") == "⛔ Usas demasiado tus tarjetas, considera disminuir tus gastos."
    )
    assert mensaje_uso(None) == ""
    assert mensaje_tarjeta(False).startswith("⚠️ Cuidado, estás perdiendo dinero en intereses")
    assert mensaje_tarjeta(True).startswith("👏¡Bien!")
    assert mensaje_tarjeta(None) == ""
