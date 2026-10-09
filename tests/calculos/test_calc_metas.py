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
