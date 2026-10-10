from datetime import date
from decimal import Decimal as D

import pytest

from apps.catalogos.models import Categoria
from apps.importacion.models import Documento, MovimientoPropuesto, ReglaClasificacion
from apps.movimientos.models import MetodoPago, Movimiento
from apps.movimientos.servicios import guardar_movimiento

pytestmark = pytest.mark.django_db
HTMX = {"HX-Request": "true"}


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
        "descripcion_original": "OXXO SUC 1234",
        "descripcion": "OXXO SUC 1234",
        "monto": D("85.50"),
        "tipo": Movimiento.Tipo.GASTO,
        "categoria": catalogo.categorias["Comida"],
        "cuenta": catalogo.nomina,
        "metodo_pago": MetodoPago.TARJETA_DEBITO,
    }
    datos.update(campos)
    return MovimientoPropuesto.objects.create(**datos)


def datos_edicion(catalogo, **campos):
    datos = {
        "fecha": "2026-09-10",
        "descripcion": "Gasolina",
        "monto": "85.50",
        "tipo": "gasto",
        "metodo_pago": "tarjeta_debito",
        "concepto": catalogo.gasolina.pk,
        "cuenta": catalogo.nomina.pk,
    }
    datos.update(campos)
    return datos


def test_editar_una_propuesta(cliente, catalogo, documento):
    pendiente = propuesta(catalogo, documento)

    respuesta = cliente.post(
        f"/importar/propuesta/{pendiente.pk}/", datos_edicion(catalogo), headers=HTMX
    )

    assert respuesta.status_code == 204
    pendiente.refresh_from_db()
    assert (pendiente.concepto, pendiente.descripcion) == (catalogo.gasolina, "Gasolina")


def test_editar_con_categoria_de_otro_hogar_es_error(cliente, catalogo, documento, otro_hogar):
    ajena = Categoria.objects.create(hogar=otro_hogar, nombre="Ajena")
    pendiente = propuesta(catalogo, documento)

    respuesta = cliente.post(
        f"/importar/propuesta/{pendiente.pk}/",
        datos_edicion(catalogo, concepto="", categoria=ajena.pk),
        headers=HTMX,
    )

    assert respuesta.status_code == 200
    assert "categoria" in respuesta.context["formulario"].errors


def test_aceptar_y_recordar(cliente, catalogo, documento):
    pendiente = propuesta(catalogo, documento)

    respuesta = cliente.post(
        f"/importar/propuesta/{pendiente.pk}/aceptar/", {"recordar": "on"}, headers=HTMX
    )

    assert respuesta.status_code == 204
    assert Movimiento.objects.get().origen == Movimiento.Origen.IMPORTADO
    assert ReglaClasificacion.objects.get().patron == "oxxo suc"


def test_aceptar_una_propuesta_invalida_muestra_el_error(cliente, catalogo, documento):
    incompleta = propuesta(catalogo, documento, categoria=None)

    cliente.post(f"/importar/propuesta/{incompleta.pk}/aceptar/", headers=HTMX)

    assert not Movimiento.objects.exists()
    contenido = cliente.get(f"/importar/{documento.pk}/").content.decode()
    assert "No se pudo aceptar" in contenido


def test_descartar(cliente, catalogo, documento):
    pendiente = propuesta(catalogo, documento)

    cliente.post(f"/importar/propuesta/{pendiente.pk}/descartar/", headers=HTMX)

    pendiente.refresh_from_db()
    assert pendiente.estado == MovimientoPropuesto.Estado.DESCARTADO


def test_aceptar_todo_lo_no_duplicado(cliente, catalogo, documento):
    existente = guardar_movimiento(
        Movimiento(
            hogar=documento.hogar,
            tipo=Movimiento.Tipo.GASTO,
            monto=D("999"),
            concepto=catalogo.gasolina,
            fecha=date(2026, 9, 10),
        )
    )
    propuesta(catalogo, documento)
    duplicada = propuesta(catalogo, documento, monto=D("999"), posible_duplicado_de=existente)

    cliente.post(f"/importar/{documento.pk}/aceptar-todo/", headers=HTMX)

    duplicada.refresh_from_db()
    assert duplicada.estado == MovimientoPropuesto.Estado.PENDIENTE
    assert Movimiento.objects.count() == 2


def test_descartar_todo(cliente, catalogo, documento):
    propuesta(catalogo, documento)

    cliente.post(f"/importar/{documento.pk}/descartar-todo/", headers=HTMX)

    documento.refresh_from_db()
    assert documento.estado == Documento.Estado.DESCARTADO


def test_actualizar_el_saldo_desde_la_pantalla(cliente, catalogo, documento):
    documento.cuenta = catalogo.tarjeta
    documento.saldo_al_corte = D("7000.00")
    documento.periodo_fin = date(2026, 10, 5)
    documento.save()

    respuesta = cliente.post(f"/importar/{documento.pk}/saldo/")

    assert respuesta.status_code == 302
    catalogo.tarjeta.refresh_from_db()
    assert catalogo.tarjeta.saldo_actual == D("7000.00")


def test_propuesta_de_otro_hogar_da_404(cliente, catalogo, otro_hogar):
    documento_ajeno = Documento.objects.create(
        hogar=otro_hogar, nombre_original="a.pdf", sha256="b" * 64
    )
    ajena = MovimientoPropuesto.objects.create(
        hogar=otro_hogar,
        documento=documento_ajeno,
        fecha=date(2026, 9, 10),
        descripcion_original="X",
        descripcion="X",
        monto=D("1"),
        tipo=Movimiento.Tipo.GASTO,
    )

    assert cliente.get(f"/importar/propuesta/{ajena.pk}/").status_code == 404
    assert cliente.post(f"/importar/propuesta/{ajena.pk}/aceptar/").status_code == 404
    assert cliente.post(f"/importar/{documento_ajeno.pk}/aceptar-todo/").status_code == 404


def test_una_propuesta_aceptada_ya_no_se_edita(cliente, catalogo, documento):
    pendiente = propuesta(catalogo, documento)
    cliente.post(f"/importar/propuesta/{pendiente.pk}/aceptar/", headers=HTMX)

    assert cliente.get(f"/importar/propuesta/{pendiente.pk}/", headers=HTMX).status_code == 404


def test_la_pantalla_muestra_duplicados_y_acciones(cliente, catalogo, documento):
    existente = guardar_movimiento(
        Movimiento(
            hogar=documento.hogar,
            tipo=Movimiento.Tipo.GASTO,
            monto=D("85.50"),
            concepto=catalogo.gasolina,
            fecha=date(2026, 9, 10),
        )
    )
    propuesta(catalogo, documento, posible_duplicado_de=existente)

    contenido = cliente.get(f"/importar/{documento.pk}/").content.decode()

    for texto in ("Posible duplicado", "Aceptar todo lo no duplicado", "Recordar clasificación"):
        assert texto in contenido
