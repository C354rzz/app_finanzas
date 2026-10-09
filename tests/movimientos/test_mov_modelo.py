from decimal import Decimal as D

import pytest
from django.core.exceptions import ValidationError
from django.db.models import RestrictedError

from apps.catalogos.models import Categoria, Persona
from apps.movimientos.models import (
    MetodoPago,
    Movimiento,
    TipoIngreso,
    es_extraordinario_por_defecto,
)

pytestmark = pytest.mark.django_db


def gasto(catalogo, **campos):
    datos = {
        "hogar": catalogo.gasolina.hogar,
        "tipo": Movimiento.Tipo.GASTO,
        "monto": D("500"),
        "concepto": catalogo.gasolina,
    }
    datos.update(campos)
    return Movimiento(**datos)


def entre_cuentas(catalogo, tipo, origen, destino):
    return Movimiento(
        hogar=catalogo.nomina.hogar,
        tipo=tipo,
        monto=D("1000"),
        metodo_pago=MetodoPago.TRANSFERENCIA,
        cuenta=origen,
        cuenta_destino=destino,
    )


def errores(movimiento):
    with pytest.raises(ValidationError) as error:
        movimiento.full_clean()
    return error.value.message_dict


def test_gasto_con_concepto_toma_su_categoria(catalogo):
    movimiento = gasto(catalogo)

    movimiento.full_clean()

    assert movimiento.categoria == catalogo.categorias["Transporte"]


def test_gasto_sin_categoria_ni_concepto_es_invalido(catalogo):
    assert "categoria" in errores(gasto(catalogo, concepto=None))


def test_concepto_de_otra_categoria_es_invalido(catalogo):
    assert "concepto" in errores(gasto(catalogo, categoria=catalogo.categorias["Comida"]))


def test_monto_debe_ser_positivo(catalogo):
    assert "monto" in errores(gasto(catalogo, monto=D("0")))


def test_ingreso_requiere_tipo_de_ingreso(catalogo):
    ingreso = Movimiento(hogar=catalogo.nomina.hogar, tipo=Movimiento.Tipo.INGRESO, monto=D("1000"))

    assert "tipo_ingreso" in errores(ingreso)


def test_solo_los_ingresos_llevan_tipo_de_ingreso(catalogo):
    assert "tipo_ingreso" in errores(gasto(catalogo, tipo_ingreso=TipoIngreso.BONO))


def test_transferencia_requiere_dos_cuentas_distintas(catalogo):
    tipo = Movimiento.Tipo.TRANSFERENCIA

    assert "cuenta" in errores(entre_cuentas(catalogo, tipo, None, catalogo.efectivo))
    assert "cuenta_destino" in errores(entre_cuentas(catalogo, tipo, catalogo.nomina, None))
    misma = entre_cuentas(catalogo, tipo, catalogo.nomina, catalogo.nomina)
    assert "cuenta_destino" in errores(misma)


def test_pago_de_deuda_va_a_una_tarjeta_o_prestamo(catalogo):
    tipo = Movimiento.Tipo.PAGO_DEUDA

    a_efectivo = entre_cuentas(catalogo, tipo, catalogo.nomina, catalogo.efectivo)
    assert "cuenta_destino" in errores(a_efectivo)
    entre_cuentas(catalogo, tipo, catalogo.nomina, catalogo.tarjeta).full_clean()
    entre_cuentas(catalogo, tipo, catalogo.nomina, catalogo.prestamo).full_clean()


def test_un_gasto_no_lleva_cuenta_destino(catalogo):
    assert "cuenta_destino" in errores(gasto(catalogo, cuenta_destino=catalogo.tarjeta))


def test_persona_de_otro_hogar_es_invalida(catalogo, otro_hogar):
    ajena = Persona.objects.create(hogar=otro_hogar, nombre="Ajena")

    assert "persona" in errores(gasto(catalogo, persona=ajena))


def test_descripcion_vacia_toma_el_nombre_del_concepto(catalogo):
    movimiento = gasto(catalogo)
    movimiento.full_clean()
    movimiento.save()

    assert movimiento.descripcion == "Gasolina"


def test_descripcion_vacia_de_un_ingreso_toma_el_tipo(catalogo):
    ingreso = Movimiento(
        hogar=catalogo.nomina.hogar,
        tipo=Movimiento.Tipo.INGRESO,
        tipo_ingreso=TipoIngreso.AGUINALDO,
        monto=D("20000"),
    )
    ingreso.full_clean()
    ingreso.save()

    assert ingreso.descripcion == "Aguinaldo"


def test_extraordinarios_por_defecto():
    assert es_extraordinario_por_defecto(TipoIngreso.AGUINALDO)
    assert es_extraordinario_por_defecto(TipoIngreso.PTU)
    assert es_extraordinario_por_defecto(TipoIngreso.PRESTAMO_RECIBIDO)
    assert not es_extraordinario_por_defecto(TipoIngreso.SALARIO)


def test_borrar_el_hogar_borra_sus_movimientos(catalogo, hogar):
    movimiento = gasto(catalogo)
    movimiento.full_clean()
    movimiento.save()

    hogar.delete()

    assert not Movimiento.objects.exists()
    assert not Categoria.objects.exists()


def test_persona_con_movimientos_no_se_puede_borrar(catalogo):
    movimiento = gasto(catalogo, persona=catalogo.monze)
    movimiento.full_clean()
    movimiento.save()

    with pytest.raises(RestrictedError):
        catalogo.monze.delete()
