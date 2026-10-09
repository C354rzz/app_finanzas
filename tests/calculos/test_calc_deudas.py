from decimal import Decimal as D

import pytest

from apps.calculos.comun import redondear
from apps.calculos.deudas import (
    NIVEL_BUENO,
    NIVEL_CUIDADO,
    NIVEL_RIESGO,
    TarjetaCredito,
    nivel_de_uso,
    patrimonio_neto,
    porcentaje_completado,
    uso_de_credito,
)

TARJETAS_EXCEL = [
    TarjetaCredito(saldo=D("2000"), linea=D("2000")),
    TarjetaCredito(saldo=D("681.99"), linea=D("900")),
    TarjetaCredito(saldo=D("1157.02"), linea=D("1200")),
    TarjetaCredito(saldo=D("3000"), linea=D("3000")),
]


def test_porcentaje_completado_del_excel():
    assert redondear(porcentaje_completado(D("41130"), D("38679.72")) * 100) == D("5.96")


def test_porcentaje_completado_sin_deuda_inicial_es_none():
    assert porcentaje_completado(D("0"), D("0")) is None


def test_uso_de_credito_por_saldo_rn08():
    uso = uso_de_credito(TARJETAS_EXCEL)

    assert redondear(uso * 100) == D("96.32")
    assert nivel_de_uso(uso) == NIVEL_RIESGO


@pytest.mark.parametrize(
    ("uso", "nivel"),
    [
        (D("0"), NIVEL_BUENO),
        (D("0.2999"), NIVEL_BUENO),
        (D("0.30"), NIVEL_CUIDADO),
        (D("0.50"), NIVEL_CUIDADO),
        (D("0.5001"), NIVEL_RIESGO),
    ],
)
def test_umbrales_de_nivel(uso, nivel):
    assert nivel_de_uso(uso) == nivel


def test_sin_linea_de_credito_el_uso_es_none():
    assert uso_de_credito([]) is None
    assert uso_de_credito([TarjetaCredito(saldo=D("100"), linea=D("0"))]) is None


def test_saldo_a_favor_cuenta_como_cero():
    uso = uso_de_credito([TarjetaCredito(saldo=D("-500"), linea=D("1000"))])

    assert uso == D("0")


def test_patrimonio_neto_del_excel():
    neto = patrimonio_neto(
        activos=[D("2300000"), D("180000"), D("113519.94")],
        saldos_prestamos=[D("38679.72")],
        saldos_tarjetas=[t.saldo for t in TARJETAS_EXCEL],
    )

    assert neto == D("2548001.21")


def test_patrimonio_ignora_saldos_a_favor_de_tarjetas():
    neto = patrimonio_neto(activos=[D("1000")], saldos_prestamos=[], saldos_tarjetas=[D("-200")])

    assert neto == D("1000")
