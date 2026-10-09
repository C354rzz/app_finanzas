from datetime import date
from decimal import Decimal as D

import pytest

from apps.catalogos.models import Categoria, Persona
from apps.movimientos.consultas import Filtros, movimientos_del_mes, totales
from apps.movimientos.formularios import FormularioFiltros
from apps.movimientos.models import MetodoPago, Movimiento, TipoIngreso
from apps.movimientos.servicios import guardar_movimiento

pytestmark = pytest.mark.django_db


def registrar(hogar, **campos):
    campos.setdefault("fecha", date(2026, 10, 10))
    campos["monto"] = D(campos["monto"])
    return guardar_movimiento(Movimiento(hogar=hogar, **campos))


def gasto(catalogo, monto, **campos):
    campos.setdefault("concepto", catalogo.gasolina)
    return registrar(catalogo.gasolina.hogar, tipo=Movimiento.Tipo.GASTO, monto=monto, **campos)


def test_solo_movimientos_del_mes_y_del_hogar(catalogo, otro_hogar):
    for dia, monto in [(date(2026, 9, 30), "100"), (date(2026, 10, 1), "200"),
                       (date(2026, 10, 31), "300"), (date(2026, 11, 1), "400")]:  # fmt: skip
        gasto(catalogo, monto, fecha=dia)
    ajena = Categoria.objects.create(hogar=otro_hogar, nombre="Casa")
    registrar(otro_hogar, tipo=Movimiento.Tipo.GASTO, monto="999", categoria=ajena)

    montos = sorted(m.monto for m in movimientos_del_mes(catalogo.gasolina.hogar, 2026, 10))

    assert montos == [D("200"), D("300")]


def test_filtros_por_persona_domicilio_cuenta_metodo_y_tipo(catalogo):
    hogar = catalogo.gasolina.hogar
    de_monze = gasto(catalogo, "10", persona=catalogo.monze)
    en_fidel = gasto(catalogo, "20", domicilio=catalogo.fidel, cuenta=catalogo.efectivo)
    con_tarjeta = gasto(catalogo, "30", metodo_pago=MetodoPago.TARJETA_CREDITO)
    pago = registrar(
        hogar,
        tipo=Movimiento.Tipo.PAGO_DEUDA,
        monto="40",
        cuenta=catalogo.nomina,
        cuenta_destino=catalogo.tarjeta,
        metodo_pago=MetodoPago.TRANSFERENCIA,
    )

    def filtrar(**campos):
        return list(movimientos_del_mes(hogar, 2026, 10, Filtros(**campos)))

    assert filtrar(persona=catalogo.monze) == [de_monze]
    assert filtrar(domicilio=catalogo.fidel) == [en_fidel]
    assert filtrar(cuenta=catalogo.tarjeta) == [pago]
    assert filtrar(metodo_pago=MetodoPago.TARJETA_CREDITO) == [con_tarjeta]
    assert filtrar(tipo=Movimiento.Tipo.PAGO_DEUDA) == [pago]


def test_busqueda_por_texto_sin_distinguir_mayusculas(catalogo):
    pemex = gasto(catalogo, "10", descripcion="Carga Pemex")
    recarga = gasto(catalogo, "20", concepto=catalogo.recarga, descripcion="Telcel")
    hogar = catalogo.gasolina.hogar

    assert list(movimientos_del_mes(hogar, 2026, 10, Filtros(texto="pemex"))) == [pemex]
    assert list(movimientos_del_mes(hogar, 2026, 10, Filtros(texto="RECARGA"))) == [recarga]


def test_totales_separan_ingresos_extra_y_excluyen_transferencias_y_pagos(catalogo):
    hogar = catalogo.gasolina.hogar
    gasto(catalogo, "1500", cuenta=catalogo.efectivo)
    gasto(
        catalogo,
        "450",
        concepto=catalogo.luz_fidel,
        cuenta=catalogo.nomina,
        metodo_pago=MetodoPago.TARJETA_DEBITO,
    )
    ingreso = {"tipo": Movimiento.Tipo.INGRESO, "metodo_pago": MetodoPago.TRANSFERENCIA}
    registrar(hogar, monto="15000", tipo_ingreso=TipoIngreso.SALARIO, **ingreso)
    registrar(
        hogar, monto="20000", tipo_ingreso=TipoIngreso.AGUINALDO, es_extraordinario=True, **ingreso
    )
    registrar(
        hogar,
        tipo=Movimiento.Tipo.TRANSFERENCIA,
        monto="3000",
        cuenta=catalogo.nomina,
        cuenta_destino=catalogo.efectivo,
    )
    registrar(
        hogar,
        tipo=Movimiento.Tipo.PAGO_DEUDA,
        monto="1000",
        cuenta=catalogo.nomina,
        cuenta_destino=catalogo.tarjeta,
    )

    t = totales(movimientos_del_mes(hogar, 2026, 10))

    assert t.ingresos == D("35000")
    assert t.ingresos_extra == D("20000")
    assert t.gastos == D("1950")
    assert t.disponible == D("33050")
    assert t.por_categoria == [
        (catalogo.categorias["Casa"], D("450")),
        (catalogo.categorias["Transporte"], D("1500")),
    ]
    assert t.por_metodo == [("Efectivo", D("1500")), ("Tarjeta de débito", D("450"))]
    assert t.por_cuenta == [("Efectivo", D("1500")), ("Nómina", D("450"))]


def test_totales_de_un_mes_vacio(hogar):
    t = totales(Movimiento.objects.none())

    assert (t.ingresos, t.ingresos_extra, t.gastos, t.disponible) == (0, 0, 0, 0)
    assert t.por_categoria == t.por_metodo == t.por_cuenta == []


def test_filtros_ignoran_ids_de_otro_hogar(catalogo, otro_hogar):
    ajena = Persona.objects.create(hogar=otro_hogar, nombre="Ajena")

    formulario = FormularioFiltros(
        {"persona": ajena.pk, "texto": "luz"}, hogar=catalogo.monze.hogar
    )

    assert formulario.filtros() == Filtros(texto="luz")


def test_filtros_sin_datos(catalogo):
    assert FormularioFiltros(None, hogar=catalogo.monze.hogar).filtros() == Filtros()
