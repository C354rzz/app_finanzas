import io
import zipfile
from datetime import date
from decimal import Decimal as D

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from django_q.models import OrmQ

from apps.importacion import archivos, servicios
from apps.importacion.archivos import huella
from apps.importacion.models import Documento
from apps.importacion.servicios import costo_del_mes, registrar_archivos

pytestmark = pytest.mark.django_db


@pytest.fixture
def encolados(monkeypatch):
    lista = []
    monkeypatch.setattr(
        servicios, "async_task", lambda funcion, documento_id: lista.append((funcion, documento_id))
    )
    return lista


def subir(nombre, datos):
    return SimpleUploadedFile(nombre, datos)


def hacer_zip(miembros):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as comprimido:
        for nombre, datos in miembros.items():
            comprimido.writestr(nombre, datos)
    return buffer.getvalue()


def test_registra_un_pdf_y_lo_encola(hogar, usuario, crear_pdf, encolados):
    datos = crear_pdf("Estado de cuenta")

    documentos, rechazos = registrar_archivos(hogar, usuario, [subir("estado.pdf", datos)])

    (documento,) = documentos
    assert rechazos == []
    assert (documento.nombre_original, documento.sha256) == ("estado.pdf", huella(datos))
    assert (documento.subido_por, documento.estado) == (usuario, Documento.Estado.SUBIDO)
    with documento.archivo.open("rb") as archivo:
        assert archivo.read() == datos
    assert encolados == [("apps.importacion.tareas.procesar", documento.pk)]


def test_rechaza_un_archivo_ya_importado(hogar, usuario, crear_pdf, encolados):
    datos = crear_pdf("Estado")
    registrar_archivos(hogar, usuario, [subir("a.pdf", datos)])

    documentos, (rechazo,) = registrar_archivos(hogar, usuario, [subir("copia.pdf", datos)])

    assert documentos == []
    assert rechazo.nombre == "copia.pdf"
    assert rechazo.motivo == f"ya se importó el {timezone.localdate():%d/%m/%Y}"
    assert Documento.objects.count() == 1


def test_el_mismo_pdf_en_otro_hogar_si_se_importa(hogar, otro_hogar, usuario, crear_pdf, encolados):
    datos = crear_pdf("Estado")
    registrar_archivos(hogar, usuario, [subir("a.pdf", datos)])

    documentos, rechazos = registrar_archivos(otro_hogar, usuario, [subir("a.pdf", datos)])

    assert (len(documentos), rechazos) == (1, [])


def test_zip_con_varios_pdfs(hogar, usuario, crear_pdf, encolados):
    comprimido = hacer_zip({"estado.pdf": crear_pdf("Estado"), "factura.pdf": crear_pdf("Factura")})

    documentos, rechazos = registrar_archivos(hogar, usuario, [subir("internet.zip", comprimido)])

    assert sorted(d.nombre_original for d in documentos) == ["estado.pdf", "factura.pdf"]
    assert (rechazos, len(encolados)) == ([], 2)


def test_archivos_invalidos_o_grandes(monkeypatch, hogar, usuario, crear_pdf, encolados):
    monkeypatch.setattr(archivos, "TAMANO_MAXIMO", 200)

    _, rechazos = registrar_archivos(
        hogar,
        usuario,
        [subir("foto.jpg", b"\xff\xd8 imagen"), subir("grande.pdf", crear_pdf("Texto " * 100))],
    )

    assert [(r.nombre, r.motivo) for r in rechazos] == [
        ("foto.jpg", "no es un PDF ni un ZIP"),
        ("grande.pdf", "pesa más de 0 MB"),
    ]
    assert not Documento.objects.exists()
    assert encolados == []


def test_cuenta_elegida_al_subir(catalogo, usuario, crear_pdf, encolados):
    (documento,), _ = registrar_archivos(
        catalogo.tarjeta.hogar,
        usuario,
        [subir("tarjeta.pdf", crear_pdf("x"))],
        cuenta=catalogo.tarjeta,
    )

    assert documento.cuenta == catalogo.tarjeta


def test_encolar_crea_una_tarea_en_la_base(hogar, usuario, crear_pdf):
    registrar_archivos(hogar, usuario, [subir("estado.pdf", crear_pdf("Estado"))])

    assert OrmQ.objects.count() == 1


def test_costo_del_mes(hogar, otro_hogar):
    for destino, letra, costo in [(hogar, "a", "0.0800"), (hogar, "b", "0.0350"),
                                  (otro_hogar, "c", "1")]:  # fmt: skip
        Documento.objects.create(
            hogar=destino, nombre_original="x.pdf", sha256=letra * 64, costo_estimado_usd=D(costo)
        )

    assert costo_del_mes(hogar) == D("0.1150")
    assert costo_del_mes(hogar, date(2000, 1, 1)) == 0
