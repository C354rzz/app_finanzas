from datetime import date
from decimal import Decimal as D

import pytest

from apps.catalogos.models import Categoria
from apps.importacion.clasificacion import (
    aplicar_regla,
    buscar_duplicado,
    buscar_regla,
    normalizar,
    palabras,
    patron_sugerido,
)
from apps.importacion.models import MovimientoPropuesto, ReglaClasificacion
from apps.movimientos.models import MetodoPago, Movimiento
from apps.movimientos.servicios import guardar_movimiento

pytestmark = pytest.mark.django_db
OCTUBRE_5 = date(2026, 10, 5)


def regla(hogar, patron, **campos):
    return ReglaClasificacion.objects.create(hogar=hogar, patron=patron, **campos)


def gasto(catalogo, monto="450", fecha=OCTUBRE_5, **campos):
    return guardar_movimiento(
        Movimiento(
            hogar=catalogo.gasolina.hogar,
            tipo=Movimiento.Tipo.GASTO,
            monto=D(monto),
            concepto=catalogo.gasolina,
            fecha=fecha,
            **campos,
        )
    )


def test_normalizar_y_palabras():
    assert normalizar("  Café  OXXO\tSuc. ") == "cafe oxxo suc."
    assert palabras("OXXO SUC 1234 MTY.") == "oxxo suc mty"


def test_patron_sugerido():
    assert patron_sugerido("OXXO SUC 1234 MONTERREY") == "oxxo suc"
    assert patron_sugerido("CFE SUMINISTRADOR DE SERVICIOS") == "cfe suministrador"
    assert patron_sugerido("PAGO A TARJETA") == "pago tarjeta"
    assert patron_sugerido("12 34") == ""


def test_regla_por_palabras_completas(catalogo):
    oxxo = regla(catalogo.gasolina.hogar, "oxxo", categoria=catalogo.categorias["Comida"])
    hogar = catalogo.gasolina.hogar

    assert buscar_regla(hogar, "Banco Demo", "OXXO 1234 SUC") == oxxo
    assert buscar_regla(hogar, "Banco Demo", "OXXOGAS") is None
    assert buscar_regla(hogar, "Banco Demo", "WALMART") is None


def test_regla_limitada_al_emisor(catalogo):
    hogar = catalogo.gasolina.hogar
    pago = regla(hogar, "pago", emisor="Banco Demo")

    assert buscar_regla(hogar, "BANCO DEMO S.A.", "PAGO RECIBIDO") == pago
    assert buscar_regla(hogar, "Otro Banco", "PAGO RECIBIDO") is None


def test_gana_la_regla_de_mayor_prioridad(catalogo):
    hogar = catalogo.gasolina.hogar
    regla(hogar, "oxxo", prioridad=50)
    especifica = regla(hogar, "oxxo suc", prioridad=10)

    assert buscar_regla(hogar, "", "OXXO SUC 1234") == especifica


def test_reglas_de_otro_hogar_no_aplican(catalogo, otro_hogar):
    regla(otro_hogar, "oxxo")

    assert buscar_regla(catalogo.gasolina.hogar, "", "OXXO") is None


def test_aplicar_regla(catalogo):
    hogar = catalogo.gasolina.hogar
    con_concepto = regla(
        hogar, "pemex", concepto=catalogo.gasolina, persona=catalogo.monze, es_hormiga=True
    )
    propuesta = MovimientoPropuesto(hogar=hogar, categoria=catalogo.categorias["Comida"])

    aplicar_regla(propuesta, con_concepto)

    assert propuesta.concepto == catalogo.gasolina
    assert propuesta.categoria == catalogo.categorias["Transporte"]
    assert (propuesta.persona, propuesta.es_hormiga) == (catalogo.monze, True)
    assert (propuesta.regla, propuesta.confianza) == (con_concepto, D("1"))
    con_concepto.refresh_from_db()
    assert con_concepto.veces_aplicada == 1


def test_aplicar_regla_no_borra_lo_que_no_define(catalogo):
    hogar = catalogo.gasolina.hogar
    solo_persona = regla(hogar, "farmacia", persona=catalogo.monze)
    comida = catalogo.categorias["Comida"]
    propuesta = MovimientoPropuesto(hogar=hogar, categoria=comida)

    aplicar_regla(propuesta, solo_persona)

    assert (propuesta.categoria, propuesta.persona) == (comida, catalogo.monze)


def test_regla_con_otra_categoria_quita_el_concepto(catalogo):
    hogar = catalogo.gasolina.hogar
    salud = Categoria.objects.get(hogar=hogar, nombre="Salud")
    propuesta = MovimientoPropuesto(
        hogar=hogar, concepto=catalogo.gasolina, categoria=catalogo.categorias["Transporte"]
    )

    aplicar_regla(propuesta, regla(hogar, "farmacia", categoria=salud))

    assert (propuesta.categoria, propuesta.concepto) == (salud, None)


def test_duplicado_por_monto_fecha_y_cuenta(catalogo):
    hogar = catalogo.gasolina.hogar
    existente = gasto(catalogo, cuenta=catalogo.nomina, metodo_pago=MetodoPago.TARJETA_DEBITO)

    assert buscar_duplicado(hogar, date(2026, 10, 7), D("450"), catalogo.nomina) == existente
    assert buscar_duplicado(hogar, date(2026, 10, 3), D("450"), None) == existente
    assert buscar_duplicado(hogar, date(2026, 10, 8), D("450"), catalogo.nomina) is None
    assert buscar_duplicado(hogar, OCTUBRE_5, D("451"), catalogo.nomina) is None
    assert buscar_duplicado(hogar, OCTUBRE_5, D("450"), catalogo.efectivo) is None


def test_duplicado_contra_movimiento_sin_cuenta(catalogo):
    existente = gasto(catalogo)

    hogar = catalogo.gasolina.hogar
    assert buscar_duplicado(hogar, OCTUBRE_5, D("450"), catalogo.nomina) == existente


def test_duplicado_por_cuenta_destino(catalogo):
    pago = guardar_movimiento(
        Movimiento(
            hogar=catalogo.tarjeta.hogar,
            tipo=Movimiento.Tipo.PAGO_DEUDA,
            monto=D("1000"),
            cuenta=catalogo.nomina,
            cuenta_destino=catalogo.tarjeta,
            fecha=OCTUBRE_5,
        )
    )

    assert buscar_duplicado(catalogo.tarjeta.hogar, OCTUBRE_5, D("1000"), catalogo.tarjeta) == pago


def test_movimientos_de_otro_hogar_no_son_duplicados(catalogo, otro_hogar):
    ajena = Categoria.objects.create(hogar=otro_hogar, nombre="Casa")
    guardar_movimiento(
        Movimiento(
            hogar=otro_hogar,
            tipo=Movimiento.Tipo.GASTO,
            monto=D("450"),
            categoria=ajena,
            fecha=OCTUBRE_5,
        )
    )

    assert buscar_duplicado(catalogo.gasolina.hogar, OCTUBRE_5, D("450")) is None
