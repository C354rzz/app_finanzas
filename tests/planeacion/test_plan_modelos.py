from decimal import Decimal as D

import pytest
from django.core.exceptions import ValidationError

from apps.calculos.comun import redondear
from apps.catalogos.models import Cuenta, Domicilio
from apps.planeacion.models import Activo, MetaAhorro, SimulacionCredito

pytestmark = pytest.mark.django_db


def meta(hogar, **campos):
    datos = {"hogar": hogar, "nombre": "Regalo", "monto_objetivo": D("20000")}
    datos.update(campos)
    return MetaAhorro(**datos)


def errores(objeto):
    with pytest.raises(ValidationError) as error:
        objeto.full_clean()
    return error.value.message_dict


def test_aporte_mensual_de_la_meta_del_excel(hogar):
    regalo = meta(hogar)

    regalo.full_clean()

    assert (regalo.meses, regalo.tasa_anual, regalo.ahorro_actual) == (12, D("0.10"), 0)
    assert redondear(regalo.aporte_mensual()) == D("1591.65")


def test_meta_ya_alcanzada_requiere_cero(hogar):
    assert meta(hogar, ahorro_actual=D("25000")).aporte_mensual() == 0


@pytest.mark.parametrize(
    ("campo", "valor"),
    [("meses", 0), ("meses", 601), ("monto_objetivo", D("0")), ("tasa_anual", D("-0.01")),
     ("ahorro_actual", D("-1"))],
)  # fmt: skip
def test_meta_con_datos_invalidos(hogar, campo, valor):
    assert campo in errores(meta(hogar, **{campo: valor}))


def test_meta_con_cuenta_de_otro_hogar_es_invalida(hogar, otro_hogar):
    ajena = Cuenta.objects.create(hogar=otro_hogar, nombre="Ajena", tipo=Cuenta.Tipo.AHORRO)

    assert "cuenta" in errores(meta(hogar, cuenta=ajena))


def test_activo_con_valor_negativo_o_domicilio_ajeno(hogar, otro_hogar):
    ajeno = Domicilio.objects.create(hogar=otro_hogar, alias="Ajeno")

    assert "valor_actual" in errores(Activo(hogar=hogar, nombre="Auto", valor_actual=D("-1")))
    assert "domicilio" in errores(
        Activo(hogar=hogar, nombre="Casa", valor_actual=D("1"), domicilio=ajeno)
    )


def test_simulacion_reproduce_el_simulador_del_excel(hogar):
    simulacion = SimulacionCredito(
        hogar=hogar,
        nombre="Préstamo personal",
        monto=D("30000"),
        tasa_anual=D("0.25"),
        meses=12,
        comision_apertura=D("0.015"),
    )

    simulacion.full_clean()
    tabla = simulacion.amortizacion()

    assert tabla.capital_inicial == D("30450")
    assert redondear(tabla.mensualidad) == D("2857.62")
    assert redondear(tabla.total_intereses) == D("3841.45")


def test_simulacion_lee_los_pagos_anticipados(hogar):
    simulacion = SimulacionCredito(
        hogar=hogar,
        nombre="Con abono",
        monto=D("30000"),
        tasa_anual=D("0.25"),
        meses=12,
        pagos_anticipados={"3": "5000.00"},
    )

    assert simulacion.anticipados() == {3: D("5000.00")}
    assert simulacion.amortizacion().filas[2].pago_anticipado == D("5000.00")


@pytest.mark.parametrize("pagos", [{"13": "100"}, {"tres": "100"}, {"2": "mucho"}, {"2": "-5"}])
def test_simulacion_con_pagos_anticipados_invalidos(hogar, pagos):
    simulacion = SimulacionCredito(
        hogar=hogar, nombre="X", monto=D("1000"), tasa_anual=D("0.1"), meses=12,
        pagos_anticipados=pagos,
    )  # fmt: skip

    assert "__all__" in errores(simulacion)


def test_simulacion_con_plazo_excesivo(hogar):
    simulacion = SimulacionCredito(
        hogar=hogar, nombre="X", monto=D("1000"), tasa_anual=D("0.1"), meses=601
    )

    assert "meses" in errores(simulacion)


def test_borrar_el_hogar_borra_su_planeacion(hogar):
    meta(hogar).save()
    Activo.objects.create(hogar=hogar, nombre="Auto", valor_actual=D("150000"))
    SimulacionCredito.objects.create(
        hogar=hogar, nombre="X", monto=D("1000"), tasa_anual=D("0.1"), meses=12
    )

    hogar.delete()

    assert not MetaAhorro.objects.exists()
    assert not Activo.objects.exists()
    assert not SimulacionCredito.objects.exists()


def test_borrar_la_cuenta_de_una_meta_conserva_la_meta(hogar):
    ahorro = Cuenta.objects.create(hogar=hogar, nombre="Ahorro", tipo=Cuenta.Tipo.AHORRO)
    regalo = meta(hogar, cuenta=ahorro)
    regalo.save()

    ahorro.delete()

    regalo.refresh_from_db()
    assert regalo.cuenta is None
