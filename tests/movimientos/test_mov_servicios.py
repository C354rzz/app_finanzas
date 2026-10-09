from decimal import Decimal as D

import pytest
from django.core.exceptions import ValidationError
from django.urls import reverse

from apps.movimientos.models import MetodoPago, Movimiento
from apps.movimientos.servicios import eliminar_movimiento, guardar_movimiento, valores_sugeridos

pytestmark = pytest.mark.django_db


def pago(catalogo, monto="1000", destino=None):
    return Movimiento(
        hogar=catalogo.tarjeta.hogar,
        tipo=Movimiento.Tipo.PAGO_DEUDA,
        monto=D(monto),
        metodo_pago=MetodoPago.TRANSFERENCIA,
        cuenta=catalogo.nomina,
        cuenta_destino=destino or catalogo.tarjeta,
    )


def saldo(cuenta):
    cuenta.refresh_from_db()
    return cuenta.saldo_actual


def test_pago_de_deuda_reduce_el_saldo_de_la_tarjeta(catalogo):
    guardar_movimiento(pago(catalogo))

    assert saldo(catalogo.tarjeta) == D("5839.01")


def test_editar_el_monto_ajusta_el_saldo_una_sola_vez(catalogo):
    movimiento = guardar_movimiento(pago(catalogo))

    movimiento.monto = D("1500")
    guardar_movimiento(movimiento)

    assert saldo(catalogo.tarjeta) == D("5339.01")


def test_cambiar_la_cuenta_destino_mueve_el_efecto(catalogo):
    movimiento = guardar_movimiento(pago(catalogo))

    movimiento.cuenta_destino = catalogo.prestamo
    guardar_movimiento(movimiento)

    assert saldo(catalogo.tarjeta) == D("6839.01")
    assert saldo(catalogo.prestamo) == D("37679.72")


def test_eliminar_el_pago_devuelve_el_saldo(catalogo):
    movimiento = guardar_movimiento(pago(catalogo))

    eliminar_movimiento(movimiento)

    assert saldo(catalogo.tarjeta) == D("6839.01")
    assert not Movimiento.objects.exists()


def test_un_gasto_con_tarjeta_no_cambia_saldos(catalogo):
    guardar_movimiento(
        Movimiento(
            hogar=catalogo.tarjeta.hogar,
            tipo=Movimiento.Tipo.GASTO,
            monto=D("300"),
            concepto=catalogo.gasolina,
            cuenta=catalogo.tarjeta,
            metodo_pago=MetodoPago.TARJETA_CREDITO,
        )
    )

    assert saldo(catalogo.tarjeta) == D("6839.01")


def test_un_movimiento_invalido_no_toca_saldos(catalogo):
    movimiento = guardar_movimiento(pago(catalogo))

    movimiento.cuenta_destino = catalogo.efectivo
    with pytest.raises(ValidationError):
        guardar_movimiento(movimiento)

    assert saldo(catalogo.tarjeta) == D("5839.01")
    assert saldo(catalogo.efectivo) == D("0")


def test_guarda_quien_lo_registro(catalogo, usuario):
    movimiento = guardar_movimiento(pago(catalogo), usuario=usuario)

    assert movimiento.creado_por == usuario


def test_valores_sugeridos_del_concepto(catalogo):
    assert valores_sugeridos(catalogo.luz_fidel) == {
        "categoria": catalogo.categorias["Casa"].pk,
        "cuenta": catalogo.nomina.pk,
        "persona": None,
        "domicilio": catalogo.fidel.pk,
        "es_hormiga": False,
        "metodo_pago": MetodoPago.TARJETA_DEBITO,
    }


def test_concepto_sin_valores_sugiere_efectivo(catalogo):
    sugeridos = valores_sugeridos(catalogo.gasolina)

    assert sugeridos["cuenta"] is None
    assert sugeridos["metodo_pago"] == MetodoPago.EFECTIVO


def test_borrar_desde_el_admin_devuelve_el_saldo(admin_client, catalogo):
    movimiento = guardar_movimiento(pago(catalogo))

    admin_client.post(
        reverse("admin:movimientos_movimiento_delete", args=[movimiento.pk]), {"post": "yes"}
    )

    assert saldo(catalogo.tarjeta) == D("6839.01")
