from datetime import date
from decimal import Decimal as D

import pytest

from apps.calculos.comun import redondear
from apps.catalogos.models import Categoria
from apps.movimientos.models import MetodoPago, Movimiento, TipoIngreso
from apps.movimientos.servicios import guardar_movimiento
from apps.presupuesto.models import PlantillaGasto, PlantillaIngreso
from apps.presupuesto.servicios import obtener_plantilla
from apps.tablero.servicios import armar_tablero

pytestmark = pytest.mark.django_db


def registrar(hogar, **campos):
    campos.setdefault("fecha", date(2026, 10, 5))
    campos["monto"] = D(campos["monto"])
    return guardar_movimiento(Movimiento(hogar=hogar, **campos))


def gasto(hogar, monto, **campos):
    return registrar(hogar, tipo=Movimiento.Tipo.GASTO, monto=monto, **campos)


def ingreso(hogar, monto, tipo_ingreso, **campos):
    return registrar(
        hogar,
        tipo=Movimiento.Tipo.INGRESO,
        monto=monto,
        tipo_ingreso=tipo_ingreso,
        metodo_pago=MetodoPago.TRANSFERENCIA,
        **campos,
    )


def filas(tablero):
    return {fila.categoria.nombre: fila for fila in tablero.categorias}


def mensajes(tablero):
    return " | ".join(alerta.mensaje for alerta in tablero.alertas)


def test_tablero_con_el_presupuesto_del_excel(plantilla_excel, hogar):
    t = armar_tablero(hogar, 2026, 10)

    assert t.resumen.ingresos_totales == D("32977.52")
    assert t.resumen.gastos_totales == D("29235")
    assert t.gasto_anual_estimado == D("350820")
    assert t.mensaje_disponible[0] == "bien"
    assert len(t.categorias) == 12
    assert filas(t)["Comida"].presupuesto == D("10600")
    assert redondear(filas(t)["Comida"].participacion, 4) == D("0.3626")


def test_ingresos_reales_incluyen_extraordinarios_sin_cambiar_la_meta(plantilla_excel, hogar):
    ingreso(hogar, "15000", TipoIngreso.SALARIO)
    ingreso(hogar, "20000", TipoIngreso.AGUINALDO, es_extraordinario=True)

    t = armar_tablero(hogar, 2026, 10)

    assert t.reales.ingresos == D("35000")
    assert t.reales.ingresos_extra == D("20000")
    assert t.resumen.meta_ahorro == D("1648.876")


def test_avance_y_color_por_categoria(plantilla_excel, catalogo, hogar):
    gasto(hogar, "1920", concepto=catalogo.gasolina)
    gasto(hogar, "100", categoria=catalogo.categorias["Viajes"])

    t = armar_tablero(hogar, 2026, 10)

    transporte = filas(t)["Transporte"]
    assert (transporte.presupuesto, transporte.gastado, transporte.restante) == (
        D("2400"),
        D("1920"),
        D("480"),
    )
    assert transporte.avance == D("0.8")
    assert transporte.color == "ambar"
    assert filas(t)["Viajes"].color == "rojo"


def test_filtro_por_domicilio(plantilla_excel, catalogo, hogar):
    PlantillaGasto.objects.create(
        hogar=hogar, plantilla=plantilla_excel, concepto=catalogo.luz_fidel, monto=D("500")
    )
    gasto(hogar, "450", concepto=catalogo.luz_fidel, domicilio=catalogo.fidel)
    gasto(hogar, "650", concepto=catalogo.gasolina)

    t = armar_tablero(hogar, 2026, 10, domicilio=catalogo.fidel)

    assert t.filtrado
    assert (t.resumen.gastos_totales, t.resumen.ingresos_totales) == (D("500"), D("0"))
    assert t.reales.gastos == D("450")
    assert (filas(t)["Casa"].presupuesto, filas(t)["Casa"].gastado) == (D("500"), D("450"))
    assert t.mensaje_disponible is None
    assert "meta de ahorro" not in mensajes(t)
    assert "más de gastos que de ingresos" not in mensajes(t)


def test_alertas_de_tarjetas(catalogo, hogar):
    t = armar_tablero(hogar, 2026, 10)

    assert "96.32%" in mensajes(t)
    assert "intereses en Tarjeta Oro" in mensajes(t)


def test_alerta_de_gastos_mayores_a_ingresos(catalogo, hogar):
    gasto(hogar, "650", concepto=catalogo.gasolina)

    assert "$650.00 más de gastos que de ingresos" in mensajes(armar_tablero(hogar, 2026, 10))


def test_alerta_de_meta_no_alcanzable(catalogo, hogar):
    plantilla = obtener_plantilla(hogar)
    PlantillaIngreso.objects.create(
        hogar=hogar, plantilla=plantilla, nombre="Salario", monto=D("1000")
    )
    PlantillaGasto.objects.create(
        hogar=hogar, plantilla=plantilla, concepto=catalogo.gasolina, monto=D("990")
    )

    t = armar_tablero(hogar, 2026, 10)

    assert "te faltan $40.00 al mes" in mensajes(t)


def test_datos_de_otro_hogar_no_aparecen(plantilla_excel, hogar, otro_hogar):
    ajena = Categoria.objects.create(hogar=otro_hogar, nombre="Casa")
    gasto(otro_hogar, "999", categoria=ajena)

    assert armar_tablero(hogar, 2026, 10).reales.gastos == 0


def test_mes_invalido(hogar):
    with pytest.raises(ValueError):
        armar_tablero(hogar, 2026, 13)
