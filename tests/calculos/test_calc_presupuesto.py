from decimal import Decimal as D

import pytest

from apps.calculos.comun import redondear
from apps.calculos.presupuesto import (
    ANUAL,
    LineaGasto,
    LineaIngreso,
    resumir_presupuesto,
)


def g(monto, fijo=False, tarjeta=False, hormiga=False):
    return LineaGasto(monto=D(monto), es_fijo=fijo, con_tarjeta=tarjeta, es_hormiga=hormiga)


# Renglones del presupuesto del Excel 2026 del usuario (sin nombres), por categoría.
GASTOS_EXCEL = [
    # Casa
    g("200", fijo=True), g("100"), g("1500", fijo=True), g("1100", fijo=True),
    g("500", fijo=True), g("500", fijo=True), g("100", fijo=True),
    # Comida
    g("3000", fijo=True), g("3000", fijo=True), g("1600", fijo=True), g("2000", fijo=True),
    g("600", hormiga=True), g("400", hormiga=True),
    # Familia
    g("4641", fijo=True), g("800", fijo=True),
    # Transporte
    g("1400", fijo=True), g("1000", fijo=True),
    # Deudas
    g("1500", fijo=True), g("2000", fijo=True),
    # Salud
    g("1000", fijo=True),
    # Suscripciones
    g("239", tarjeta=True, hormiga=True), g("10", tarjeta=True), g("49", tarjeta=True),
    g("196", fijo=True),
    # Entretenimiento
    g("500", hormiga=True),
    # Otros
    g("300", fijo=True), g("500", tarjeta=True, hormiga=True), g("500", tarjeta=True, hormiga=True),
]  # fmt: skip
INGRESOS_EXCEL = [LineaIngreso(monto=D("32977.52"), es_fijo=True)]


def test_reproduce_los_valores_del_excel():
    r = resumir_presupuesto(INGRESOS_EXCEL, GASTOS_EXCEL, D("0.05"))

    assert r.ingresos_fijos == D("32977.52")
    assert r.ingresos_variables == D("0")
    assert r.ingresos_totales == D("32977.52")
    assert r.gastos_totales == D("29235")
    assert r.gastos_fijos == D("26337")
    assert r.gastos_variables == D("2898")
    assert r.disponible == D("3742.52")
    assert r.meta_ahorro == D("1648.876")
    assert r.presupuesto_hormiga == D("2739")
    assert redondear(r.maximo_diario_hormiga) == D("91.30")
    assert r.recorte_necesario is None
    assert r.gasto_con_tarjeta == D("1298")


def test_recorte_necesario_cuando_el_disponible_no_alcanza_la_meta():
    r = resumir_presupuesto([LineaIngreso(D("10000"))], [g("9500")], D("0.10"))

    assert r.disponible == D("500")
    assert r.meta_ahorro == D("1000")
    assert r.recorte_necesario == D("500")


def test_gasto_anual_se_prorratea_entre_12_en_todos_los_totales():
    anual = LineaGasto(monto=D("1200"), periodicidad=ANUAL, es_fijo=True, es_hormiga=True)

    assert anual.monto_mensual() == D("100")
    r = resumir_presupuesto([LineaIngreso(D("1000"))], [anual], D("0"))
    assert r.gastos_totales == D("100")
    assert r.gastos_fijos == D("100")
    assert r.presupuesto_hormiga == D("100")


def test_ingresos_variables_se_separan_de_fijos():
    r = resumir_presupuesto(
        [LineaIngreso(D("1000"), es_fijo=True), LineaIngreso(D("250"), es_fijo=False)], [], D("0")
    )

    assert r.ingresos_fijos == D("1000")
    assert r.ingresos_variables == D("250")
    assert r.ingresos_totales == D("1250")


def test_presupuesto_vacio_da_ceros():
    r = resumir_presupuesto([], [], D("0.10"))

    assert r.ingresos_totales == D("0")
    assert r.gastos_totales == D("0")
    assert r.maximo_diario_hormiga == D("0")
    assert r.recorte_necesario is None


def test_periodicidad_desconocida_es_error():
    with pytest.raises(ValueError, match="Periodicidad"):
        LineaGasto(monto=D("10"), periodicidad="semanal").monto_mensual()


@pytest.mark.parametrize("porcentaje", [D("-0.01"), D("1.01")])
def test_porcentaje_de_ahorro_fuera_de_rango_es_error(porcentaje):
    with pytest.raises(ValueError, match="porcentaje"):
        resumir_presupuesto([], [], porcentaje)


def test_montos_negativos_son_error():
    with pytest.raises(ValueError, match="negativ"):
        resumir_presupuesto([LineaIngreso(D("-1"))], [], D("0"))
    with pytest.raises(ValueError, match="negativ"):
        resumir_presupuesto([], [g("-5")], D("0"))
