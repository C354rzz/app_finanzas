from datetime import date
from decimal import Decimal as D

import pytest

from apps.calculos.comun import redondear
from apps.catalogos.models import Cuenta, TasaMercado
from apps.movimientos.models import MetodoPago, Movimiento
from apps.movimientos.servicios import guardar_movimiento
from apps.planeacion.models import Activo
from apps.planeacion.servicios import calcular_patrimonio, vista_deudas

pytestmark = pytest.mark.django_db


def test_tarjetas_y_creditos_del_hogar(catalogo):
    v = vista_deudas(catalogo.tarjeta.hogar, 2026, 10)

    (tarjeta,) = v.tarjetas
    assert tarjeta.cuenta == catalogo.tarjeta
    assert redondear(tarjeta.uso, 4) == D("0.9632")
    assert tarjeta.nivel == "riesgo"
    assert tarjeta.mensaje.startswith("⚠️ Cuidado, estás perdiendo dinero")
    assert (tarjeta.tasa, tarjeta.tasa_de_mercado) == (None, False)
    (credito,) = v.creditos
    assert redondear(credito.completado, 4) == D("0.0596")
    assert v.resumen.total_tarjetas + v.resumen.total_creditos == D("45518.73")
    assert v.mensaje_uso.startswith("⛔ Usas demasiado")


def test_tasa_promedio_del_mercado(hogar):
    TasaMercado.objects.create(
        institucion="Banco Demo", producto="Clásica", tasa_promedio=D("0.45")
    )
    Cuenta.objects.create(
        hogar=hogar,
        nombre="Demo",
        tipo=Cuenta.Tipo.CREDITO,
        institucion="Banco Demo",
        producto="Clásica",
        linea_credito=D("10000"),
    )

    (tarjeta,) = vista_deudas(hogar, 2026, 10).tarjetas

    assert (tarjeta.tasa, tarjeta.tasa_de_mercado) == (D("0.45"), True)


def test_sin_linea_ni_monto_inicial_no_truena(hogar):
    Cuenta.objects.create(
        hogar=hogar, nombre="Sin línea", tipo=Cuenta.Tipo.CREDITO, saldo_actual=D("-50")
    )
    Cuenta.objects.create(hogar=hogar, nombre="Sin inicial", tipo=Cuenta.Tipo.PRESTAMO)

    v = vista_deudas(hogar, 2026, 10)

    assert (v.tarjetas[0].uso, v.tarjetas[0].nivel) == (None, None)
    assert v.creditos[0].completado is None
    assert v.resumen.total_tarjetas == 0


def test_gasto_con_tarjeta_presupuestado_y_real(plantilla_excel, catalogo, hogar):
    for monto, metodo in [("300", MetodoPago.TARJETA_CREDITO), ("100", MetodoPago.EFECTIVO)]:
        guardar_movimiento(
            Movimiento(
                hogar=hogar,
                tipo=Movimiento.Tipo.GASTO,
                monto=D(monto),
                concepto=catalogo.gasolina,
                metodo_pago=metodo,
                fecha=date(2026, 10, 5),
            )
        )

    v = vista_deudas(hogar, 2026, 10)

    assert v.gasto_tarjeta_presupuesto == D("1298")
    assert v.gasto_tarjeta_real == D("300")


def test_hogar_sin_deudas(hogar):
    v = vista_deudas(hogar, 2026, 10)

    assert (v.tarjetas, v.creditos, v.mensaje_uso) == ([], [], "")


def test_patrimonio_neto_del_excel(catalogo, hogar, otro_hogar):
    for nombre, valor in [("Casa", "2400000"), ("Auto", "150000"), ("Ahorro", "43519.94")]:
        Activo.objects.create(hogar=hogar, nombre=nombre, valor_actual=D(valor))
    Activo.objects.create(hogar=hogar, nombre="Vendido", valor_actual=D("1"), activo=False)
    Activo.objects.create(hogar=otro_hogar, nombre="Ajeno", valor_actual=D("999"))

    p = calcular_patrimonio(hogar)

    assert p.total_activos == D("2593519.94")
    assert (p.deuda_creditos, p.deuda_tarjetas) == (D("38679.72"), D("6839.01"))
    assert p.neto == D("2548001.21")
    assert len(p.activos) == 3


def test_patrimonio_de_un_hogar_vacio(hogar):
    p = calcular_patrimonio(hogar)

    assert (p.activos, p.total_activos, p.neto) == ([], 0, 0)
