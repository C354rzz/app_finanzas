from decimal import Decimal as D

import pytest

from apps.calculos.comun import CERO, redondear
from apps.calculos.credito import amortizar, tasa_efectiva_mensual


def test_tasa_efectiva_mensual_del_excel():
    r = tasa_efectiva_mensual(D("0.25"))

    assert abs(r - D("0.018769265121506")) < D("1e-14")


def test_reproduce_simulador_del_excel():
    a = amortizar(D("30000"), D("0.25"), 12, comision_apertura=D("0.015"))

    assert a.capital_inicial == D("30450")
    assert redondear(a.mensualidad) == D("2857.62")
    assert redondear(a.total_intereses) == D("3841.45")
    assert len(a.filas) == 12
    assert a.filas[-1].saldo_final == CERO
    assert redondear(a.filas[-1].capital_acumulado) == D("30450.00")


def test_tasa_cero_sin_intereses():
    a = amortizar(D("1200"), D("0"), 12)

    assert a.mensualidad == D("100")
    assert a.total_intereses == CERO
    assert a.filas[-1].saldo_final == CERO


def test_pago_anticipado_reduce_intereses_y_mensualidades():
    base = amortizar(D("30000"), D("0.25"), 12, comision_apertura=D("0.015"))
    con_abono = amortizar(
        D("30000"), D("0.25"), 12, comision_apertura=D("0.015"), pagos_anticipados={3: D("5000")}
    )

    assert con_abono.filas[2].pago_anticipado == D("5000")
    assert con_abono.total_intereses < base.total_intereses
    assert con_abono.filas[3].mensualidad < con_abono.filas[1].mensualidad
    assert con_abono.filas[-1].saldo_final == CERO


def test_pago_anticipado_mayor_al_saldo_liquida_sin_saldo_negativo():
    a = amortizar(D("10000"), D("0.25"), 12, pagos_anticipados={2: D("100000")})

    assert len(a.filas) == 2
    assert a.filas[1].saldo_final == CERO
    assert a.filas[1].pago_anticipado < D("100000")
    assert all(f.saldo_final >= 0 for f in a.filas)


@pytest.mark.parametrize(
    ("kwargs", "mensaje"),
    [
        ({"monto": D("0")}, "monto"),
        ({"meses": 0}, "meses"),
        ({"tasa_anual": D("-0.1")}, "tasa"),
        ({"comision_apertura": D("-0.01")}, "comisión"),
        ({"pagos_anticipados": {13: D("100")}}, "mes"),
        ({"pagos_anticipados": {2: D("-1")}}, "anticipado"),
    ],
)
def test_entradas_invalidas(kwargs, mensaje):
    params = {"monto": D("1000"), "tasa_anual": D("0.1"), "meses": 12} | kwargs
    with pytest.raises(ValueError, match=mensaje):
        amortizar(**params)
