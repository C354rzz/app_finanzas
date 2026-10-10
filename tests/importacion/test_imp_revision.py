from datetime import date
from decimal import Decimal as D

import pytest
from django.core.exceptions import ValidationError

from apps.importacion.models import Documento, MovimientoPropuesto, ReglaClasificacion
from apps.importacion.servicios import (
    aceptar_no_duplicados,
    aceptar_propuesta,
    actualizar_saldo,
    descartar_propuesta,
    descartar_todas,
)
from apps.movimientos.models import MetodoPago, Movimiento
from apps.movimientos.servicios import guardar_movimiento

pytestmark = pytest.mark.django_db
PENDIENTE = MovimientoPropuesto.Estado.PENDIENTE


@pytest.fixture
def documento(hogar):
    return Documento.objects.create(
        hogar=hogar,
        nombre_original="estado.pdf",
        sha256="a" * 64,
        emisor="Banco Demo",
        estado=Documento.Estado.POR_REVISAR,
    )


def propuesta(catalogo, documento, **campos):
    datos = {
        "hogar": documento.hogar,
        "documento": documento,
        "fecha": date(2026, 9, 10),
        "descripcion_original": "OXXO SUC 1234 MTY",
        "descripcion": "OXXO SUC 1234 MTY",
        "monto": D("85.50"),
        "tipo": Movimiento.Tipo.GASTO,
        "categoria": catalogo.categorias["Comida"],
        "cuenta": catalogo.nomina,
        "metodo_pago": MetodoPago.TARJETA_DEBITO,
    }
    datos.update(campos)
    return MovimientoPropuesto.objects.create(**datos)


def test_aceptar_crea_el_movimiento(catalogo, documento, usuario):
    pendiente = propuesta(catalogo, documento)

    movimiento = aceptar_propuesta(pendiente, usuario)

    assert (movimiento.origen, movimiento.documento, movimiento.creado_por) == (
        Movimiento.Origen.IMPORTADO,
        documento,
        usuario,
    )
    assert (movimiento.monto, movimiento.descripcion) == (D("85.50"), "OXXO SUC 1234 MTY")
    pendiente.refresh_from_db()
    assert (pendiente.estado, pendiente.movimiento) == (
        MovimientoPropuesto.Estado.ACEPTADO,
        movimiento,
    )
    documento.refresh_from_db()
    assert documento.estado == Documento.Estado.CONFIRMADO


def test_el_documento_sigue_por_revisar_con_pendientes(catalogo, documento, usuario):
    primera = propuesta(catalogo, documento)
    propuesta(catalogo, documento, descripcion="OTRA")

    aceptar_propuesta(primera, usuario)

    documento.refresh_from_db()
    assert documento.estado == Documento.Estado.POR_REVISAR


def test_datos_incompletos_guardan_el_error(catalogo, documento, usuario):
    incompleta = propuesta(catalogo, documento, categoria=None)

    with pytest.raises(ValidationError):
        aceptar_propuesta(incompleta, usuario)

    incompleta.refresh_from_db()
    assert incompleta.estado == PENDIENTE
    assert "No se pudo aceptar" in incompleta.error
    assert "categoría del gasto" in incompleta.error
    assert not Movimiento.objects.exists()


def test_no_se_acepta_dos_veces(catalogo, documento, usuario):
    pendiente = propuesta(catalogo, documento)
    copia_vieja = MovimientoPropuesto.objects.get(pk=pendiente.pk)
    aceptar_propuesta(pendiente, usuario)

    for intento in (pendiente, copia_vieja):
        with pytest.raises(ValidationError):
            aceptar_propuesta(intento, usuario)

    assert Movimiento.objects.count() == 1


def test_aceptar_pago_de_deuda_reduce_el_saldo(catalogo, documento, usuario):
    pago = propuesta(
        catalogo,
        documento,
        tipo=Movimiento.Tipo.PAGO_DEUDA,
        categoria=None,
        monto=D("2000"),
        cuenta_destino=catalogo.tarjeta,
        metodo_pago=MetodoPago.TRANSFERENCIA,
    )

    aceptar_propuesta(pago, usuario)

    catalogo.tarjeta.refresh_from_db()
    assert catalogo.tarjeta.saldo_actual == D("4839.01")


def test_recordar_crea_una_regla(catalogo, documento, usuario):
    aceptar_propuesta(
        propuesta(catalogo, documento, persona=catalogo.monze), usuario, recordar=True
    )

    regla = ReglaClasificacion.objects.get()
    assert (regla.patron, regla.emisor) == ("oxxo suc", "Banco Demo")
    assert (regla.categoria, regla.persona) == (catalogo.categorias["Comida"], catalogo.monze)


def test_recordar_actualiza_la_regla_existente(catalogo, documento, usuario):
    aceptar_propuesta(propuesta(catalogo, documento), usuario, recordar=True)
    casa = catalogo.categorias["Casa"]

    aceptar_propuesta(propuesta(catalogo, documento, categoria=casa), usuario, recordar=True)

    assert ReglaClasificacion.objects.get().categoria == casa


def test_descartar(catalogo, documento):
    descartada = propuesta(catalogo, documento)

    descartar_propuesta(descartada)

    descartada.refresh_from_db()
    documento.refresh_from_db()
    assert descartada.estado == MovimientoPropuesto.Estado.DESCARTADO
    assert documento.estado == Documento.Estado.DESCARTADO


def test_aceptar_todo_lo_no_duplicado(catalogo, documento, usuario):
    existente = guardar_movimiento(
        Movimiento(
            hogar=documento.hogar,
            tipo=Movimiento.Tipo.GASTO,
            monto=D("999"),
            concepto=catalogo.gasolina,
            fecha=date(2026, 9, 10),
        )
    )
    buena = propuesta(catalogo, documento)
    duplicada = propuesta(catalogo, documento, monto=D("999"), posible_duplicado_de=existente)
    invalida = propuesta(catalogo, documento, categoria=None, descripcion="SIN CATEGORIA")

    assert aceptar_no_duplicados(documento, usuario) == (1, 1)

    for revisada, estado in [
        (buena, "aceptado"),
        (duplicada, "pendiente"),
        (invalida, "pendiente"),
    ]:
        revisada.refresh_from_db()
        assert revisada.estado == estado
    assert invalida.error


def test_descartar_todas(catalogo, documento):
    propuesta(catalogo, documento)
    propuesta(catalogo, documento, descripcion="OTRA")

    descartar_todas(documento)

    assert set(documento.propuestas.values_list("estado", flat=True)) == {"descartado"}
    documento.refresh_from_db()
    assert documento.estado == Documento.Estado.DESCARTADO


def test_actualizar_saldo_al_corte(catalogo, documento):
    documento.cuenta = catalogo.tarjeta
    documento.saldo_al_corte = D("7000.00")
    documento.periodo_fin = date(2026, 10, 5)
    documento.save()

    assert actualizar_saldo(documento) is True

    catalogo.tarjeta.refresh_from_db()
    assert (catalogo.tarjeta.saldo_actual, catalogo.tarjeta.fecha_saldo) == (
        D("7000.00"),
        date(2026, 10, 5),
    )


def test_sin_cuenta_no_se_actualiza_ningun_saldo(documento):
    documento.saldo_al_corte = D("1")
    documento.save()

    assert actualizar_saldo(documento) is False
