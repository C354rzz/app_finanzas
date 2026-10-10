from datetime import date
from decimal import Decimal as D

import pytest
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.db import IntegrityError

from apps.catalogos.models import Categoria
from apps.importacion.models import Documento, MovimientoPropuesto, ReglaClasificacion
from apps.movimientos.models import Movimiento
from apps.movimientos.servicios import guardar_movimiento

pytestmark = pytest.mark.django_db
HUELLA = "a" * 64


def documento(hogar, huella=HUELLA, contenido=b"%PDF-1.4 prueba"):
    doc = Documento(hogar=hogar, nombre_original="estado.pdf", sha256=huella)
    doc.archivo.save("x.pdf", ContentFile(contenido), save=False)
    doc.save()
    return doc


def test_el_archivo_se_guarda_por_hogar_y_huella(hogar):
    doc = documento(hogar)

    assert doc.archivo.name == f"documentos/{hogar.pk}/{HUELLA}.pdf"
    assert doc.estado == Documento.Estado.SUBIDO
    with doc.archivo.open("rb") as archivo:
        assert archivo.read() == b"%PDF-1.4 prueba"


def test_la_huella_es_unica_por_hogar(hogar, otro_hogar):
    documento(hogar)
    documento(otro_hogar)

    with pytest.raises(IntegrityError):
        documento(hogar)


def test_propuesta_con_categoria_de_otro_hogar_es_invalida(hogar, otro_hogar):
    ajena = Categoria.objects.create(hogar=otro_hogar, nombre="Ajena")
    propuesta = MovimientoPropuesto(
        hogar=hogar,
        documento=documento(hogar),
        fecha=date(2026, 10, 5),
        descripcion_original="OXXO",
        descripcion="OXXO",
        monto=D("85.50"),
        tipo=Movimiento.Tipo.GASTO,
        categoria=ajena,
    )

    with pytest.raises(ValidationError) as error:
        propuesta.full_clean()

    assert "categoria" in error.value.message_dict


def test_movimiento_con_documento_de_otro_hogar_es_invalido(catalogo, otro_hogar):
    movimiento = Movimiento(
        hogar=catalogo.gasolina.hogar,
        tipo=Movimiento.Tipo.GASTO,
        monto=D("10"),
        concepto=catalogo.gasolina,
        documento=documento(otro_hogar),
    )

    with pytest.raises(ValidationError) as error:
        movimiento.full_clean()

    assert "documento" in error.value.message_dict


def test_borrar_el_documento_conserva_los_movimientos(catalogo, hogar):
    doc = documento(hogar)
    movimiento = guardar_movimiento(
        Movimiento(
            hogar=hogar,
            tipo=Movimiento.Tipo.GASTO,
            monto=D("10"),
            concepto=catalogo.gasolina,
            origen=Movimiento.Origen.IMPORTADO,
            documento=doc,
        )
    )

    doc.delete()

    movimiento.refresh_from_db()
    assert movimiento.documento is None


def test_borrar_el_hogar_borra_su_importacion(catalogo, hogar):
    doc = documento(hogar)
    ReglaClasificacion.objects.create(hogar=hogar, patron="oxxo")
    MovimientoPropuesto.objects.create(
        hogar=hogar,
        documento=doc,
        fecha=date(2026, 10, 5),
        descripcion_original="OXXO",
        descripcion="OXXO",
        monto=D("1"),
        tipo=Movimiento.Tipo.GASTO,
    )

    hogar.delete()

    assert not Documento.objects.exists()
    assert not MovimientoPropuesto.objects.exists()
    assert not ReglaClasificacion.objects.exists()


def test_fabrica_de_pdfs_de_prueba(crear_pdf):
    datos = crear_pdf("Hola mundo", "Segunda página")

    assert datos.startswith(b"%PDF-1.4")
    assert datos.rstrip().endswith(b"%%EOF")
