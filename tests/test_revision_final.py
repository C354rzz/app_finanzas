"""Regresiones de la revisión final del plan 2."""

from datetime import date
from decimal import Decimal as D

import pytest
from django.core.exceptions import ValidationError

from apps.catalogos.models import Concepto, Domicilio
from apps.movimientos.models import MetodoPago, Movimiento
from apps.movimientos.servicios import eliminar_movimiento, guardar_movimiento

pytestmark = pytest.mark.django_db
HTMX = {"HX-Request": "true"}


def pago(catalogo, monto):
    return guardar_movimiento(
        Movimiento(
            hogar=catalogo.tarjeta.hogar,
            tipo=Movimiento.Tipo.PAGO_DEUDA,
            monto=D(monto),
            metodo_pago=MetodoPago.TRANSFERENCIA,
            cuenta=catalogo.nomina,
            cuenta_destino=catalogo.tarjeta,
        )
    )


def test_borrar_domicilio_usado_por_conceptos_lo_desactiva_sin_error(cliente, catalogo):
    casa = catalogo.categorias["Casa"]
    Concepto.objects.create(hogar=catalogo.fidel.hogar, categoria=casa, nombre="Luz")

    respuesta = cliente.post(f"/catalogos/domicilios/{catalogo.fidel.pk}/eliminar/", headers=HTMX)

    assert respuesta.status_code == 204
    assert Domicilio.objects.get(pk=catalogo.fidel.pk).activo is False
    catalogo.luz_fidel.refresh_from_db()
    assert catalogo.luz_fidel.domicilio == catalogo.fidel


def test_borrar_con_una_copia_vieja_revierte_el_monto_guardado(catalogo):
    original = pago(catalogo, "100")
    copia_vieja = Movimiento.objects.get(pk=original.pk)
    original.monto = D("300")
    guardar_movimiento(original)

    eliminar_movimiento(copia_vieja)

    catalogo.tarjeta.refresh_from_db()
    assert catalogo.tarjeta.saldo_actual == D("6839.01")


def test_borrar_dos_veces_no_revierte_dos_veces(catalogo):
    movimiento = pago(catalogo, "100")
    copia = Movimiento.objects.get(pk=movimiento.pk)

    eliminar_movimiento(movimiento)
    eliminar_movimiento(copia)

    catalogo.tarjeta.refresh_from_db()
    assert catalogo.tarjeta.saldo_actual == D("6839.01")


def test_formularios_bloquean_el_doble_envio(cliente, catalogo):
    captura = cliente.get("/movimientos/capturar/gasto/", headers=HTMX).content.decode()
    catalogo_form = cliente.get("/catalogos/personas/nuevo/", headers=HTMX).content.decode()

    assert "hx-disabled-elt" in captura
    assert "hx-disabled-elt" in catalogo_form


def test_sugeridos_no_preselecciona_una_cuenta_inactiva(cliente, catalogo):
    catalogo.nomina.activo = False
    catalogo.nomina.save()

    respuesta = cliente.get("/movimientos/sugeridos/", {"concepto": catalogo.luz_fidel.pk})

    assert catalogo.nomina not in respuesta.context["formulario"].fields["cuenta"].queryset


def test_fecha_fuera_de_rango_es_invalida(catalogo):
    movimiento = Movimiento(
        hogar=catalogo.gasolina.hogar,
        tipo=Movimiento.Tipo.GASTO,
        monto=D("10"),
        concepto=catalogo.gasolina,
        fecha=date(1999, 5, 1),
    )

    with pytest.raises(ValidationError) as error:
        movimiento.full_clean()

    assert "fecha" in error.value.message_dict
