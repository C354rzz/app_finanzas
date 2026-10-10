from datetime import date
from decimal import Decimal as D

import pytest
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.catalogos.models import Cuenta
from apps.importacion import servicios
from apps.importacion.archivos import huella
from apps.importacion.models import Documento, MovimientoPropuesto
from apps.movimientos.models import Movimiento
from apps.movimientos.servicios import guardar_movimiento

pytestmark = pytest.mark.django_db


@pytest.fixture
def encolados(monkeypatch):
    lista = []
    monkeypatch.setattr(
        servicios, "async_task", lambda funcion, documento_id: lista.append(documento_id)
    )
    return lista


def pdf_subido(crear_pdf, nombre="estado.pdf", texto="Estado de cuenta"):
    return SimpleUploadedFile(nombre, crear_pdf(texto), content_type="application/pdf")


def documento_con_pdf(hogar, crear_pdf, **campos):
    datos = crear_pdf("Estado de cuenta Banco Demo")
    documento = Documento(hogar=hogar, nombre_original="estado.pdf", sha256=huella(datos), **campos)
    documento.archivo.save("x.pdf", ContentFile(datos), save=False)
    documento.save()
    return documento, datos


def test_pantalla_importar(cliente, hogar):
    Documento.objects.create(
        hogar=hogar, nombre_original="viejo.pdf", sha256="a" * 64, costo_estimado_usd=D("0.0800")
    )

    contenido = cliente.get("/importar/").content.decode()

    assert "Importar documentos" in contenido
    assert "US$0.08" in contenido
    assert "viejo.pdf" in contenido


def test_subir_un_pdf(cliente, crear_pdf, encolados):
    respuesta = cliente.post("/importar/", {"archivos": pdf_subido(crear_pdf)}, follow=True)

    assert Documento.objects.count() == 1
    assert len(encolados) == 1
    assert "Se subieron 1 documento(s)" in respuesta.content.decode()


def test_subir_varios_archivos(cliente, crear_pdf, encolados):
    archivos = [pdf_subido(crear_pdf, "a.pdf", "Uno"), pdf_subido(crear_pdf, "b.pdf", "Dos")]

    cliente.post("/importar/", {"archivos": archivos})

    assert Documento.objects.count() == 2


def test_subir_un_duplicado_muestra_el_motivo(cliente, crear_pdf, encolados):
    cliente.post("/importar/", {"archivos": pdf_subido(crear_pdf)})

    respuesta = cliente.post("/importar/", {"archivos": pdf_subido(crear_pdf)}, follow=True)

    assert "ya se importó" in respuesta.content.decode()
    assert Documento.objects.count() == 1


def test_cuenta_de_otro_hogar_es_error(cliente, otro_hogar, crear_pdf, encolados):
    ajena = Cuenta.objects.create(hogar=otro_hogar, nombre="Ajena", tipo=Cuenta.Tipo.CREDITO)

    respuesta = cliente.post("/importar/", {"archivos": pdf_subido(crear_pdf), "cuenta": ajena.pk})

    assert respuesta.status_code == 200
    assert "cuenta" in respuesta.context["formulario"].errors
    assert not Documento.objects.exists()


def test_la_lista_se_actualiza_mientras_hay_documentos_en_proceso(cliente, hogar):
    documento = Documento.objects.create(hogar=hogar, nombre_original="a.pdf", sha256="a" * 64)

    assert 'hx-trigger="every 3s"' in cliente.get("/importar/documentos/").content.decode()

    Documento.objects.filter(pk=documento.pk).update(estado=Documento.Estado.POR_REVISAR)
    assert 'hx-trigger="every 3s"' not in cliente.get("/importar/documentos/").content.decode()


def test_ver_el_pdf_original(cliente, hogar, crear_pdf):
    documento, datos = documento_con_pdf(hogar, crear_pdf)

    respuesta = cliente.get(f"/importar/{documento.pk}/original/")

    assert respuesta.status_code == 200
    assert respuesta["Content-Type"] == "application/pdf"
    assert b"".join(respuesta.streaming_content) == datos


def test_pdf_de_otro_hogar_da_404(cliente, otro_hogar, crear_pdf):
    ajeno, _ = documento_con_pdf(otro_hogar, crear_pdf)

    assert cliente.get(f"/importar/{ajeno.pk}/original/").status_code == 404


def test_los_pdfs_no_tienen_url_publica(cliente, hogar, crear_pdf):
    documento, _ = documento_con_pdf(hogar, crear_pdf)

    assert cliente.get(f"/media/{documento.archivo.name}").status_code == 404


def test_reintentar_un_documento_con_error(cliente, hogar, encolados):
    documento = Documento.objects.create(
        hogar=hogar, nombre_original="a.pdf", sha256="a" * 64,
        estado=Documento.Estado.ERROR, error="Falla",
    )  # fmt: skip

    cliente.post(f"/importar/{documento.pk}/reintentar/")

    documento.refresh_from_db()
    assert (documento.estado, documento.error) == (Documento.Estado.SUBIDO, "")
    assert encolados == [documento.pk]


def test_reintentar_no_aplica_a_documentos_procesados(cliente, hogar, encolados):
    documento = Documento.objects.create(
        hogar=hogar, nombre_original="a.pdf", sha256="a" * 64, estado=Documento.Estado.POR_REVISAR
    )

    cliente.post(f"/importar/{documento.pk}/reintentar/")

    documento.refresh_from_db()
    assert (documento.estado, encolados) == (Documento.Estado.POR_REVISAR, [])


def test_eliminar_conserva_los_movimientos(cliente, catalogo, hogar, crear_pdf):
    documento, _ = documento_con_pdf(hogar, crear_pdf, estado=Documento.Estado.CONFIRMADO)
    nombre = documento.archivo.name
    movimiento = guardar_movimiento(
        Movimiento(
            hogar=hogar,
            tipo=Movimiento.Tipo.GASTO,
            monto=D("10"),
            concepto=catalogo.gasolina,
            origen=Movimiento.Origen.IMPORTADO,
            documento=documento,
        )
    )

    cliente.post(f"/importar/{documento.pk}/eliminar/")

    assert not Documento.objects.exists()
    assert not default_storage.exists(nombre)
    movimiento.refresh_from_db()
    assert movimiento.documento is None


def test_pantalla_revisar_lista_las_propuestas(cliente, catalogo, hogar):
    documento = Documento.objects.create(
        hogar=hogar, nombre_original="estado.pdf", sha256="a" * 64,
        estado=Documento.Estado.POR_REVISAR,
    )  # fmt: skip
    MovimientoPropuesto.objects.create(
        hogar=hogar,
        documento=documento,
        fecha=date(2026, 9, 10),
        descripcion_original="OXXO SUC 1234",
        descripcion="OXXO SUC 1234",
        monto=D("85.50"),
        tipo=Movimiento.Tipo.GASTO,
    )

    contenido = cliente.get(f"/importar/{documento.pk}/").content.decode()

    assert "OXXO SUC 1234" in contenido
    assert "$85.50" in contenido


def test_documento_de_otro_hogar_da_404(cliente, otro_hogar):
    ajeno = Documento.objects.create(hogar=otro_hogar, nombre_original="a.pdf", sha256="a" * 64)

    assert cliente.get(f"/importar/{ajeno.pk}/").status_code == 404
    assert cliente.post(f"/importar/{ajeno.pk}/eliminar/").status_code == 404
    assert Documento.objects.filter(pk=ajeno.pk).exists()


def test_navegacion_con_importar(cliente):
    contenido = cliente.get("/catalogos/").content.decode()

    assert "/importar/" in contenido
    assert "Presupuesto del mes" in contenido
