import hashlib
import io
import zipfile

import pytest

from apps.importacion import archivos
from apps.importacion.archivos import es_pdf, huella, pdfs_del_archivo
from apps.importacion.errores import ArchivoInvalidoError


def hacer_zip(miembros):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as comprimido:
        for nombre, datos in miembros.items():
            comprimido.writestr(nombre, datos)
    return buffer.getvalue()


def test_huella_sha256():
    assert huella(b"abc") == hashlib.sha256(b"abc").hexdigest()


def test_reconoce_un_pdf(crear_pdf):
    assert es_pdf(crear_pdf("Hola"))
    assert es_pdf(b"\n\n%PDF-1.7 resto")
    assert not es_pdf(b"hola")


def test_un_pdf_se_devuelve_tal_cual(crear_pdf):
    datos = crear_pdf("Hola")

    assert pdfs_del_archivo("estado.pdf", datos) == [("estado.pdf", datos)]


def test_zip_con_pdfs_y_otros_archivos(crear_pdf):
    estado, factura = crear_pdf("Estado"), crear_pdf("Factura")
    comprimido = hacer_zip(
        {
            "carpeta/estado.pdf": estado,
            "factura.PDF": factura,
            "leeme.txt": b"hola",
            "__MACOSX/._estado.pdf": b"basura",
            "falso.pdf": b"no soy un pdf",
        }
    )

    assert pdfs_del_archivo("internet.zip", comprimido) == [
        ("estado.pdf", estado),
        ("factura.PDF", factura),
    ]


def test_archivo_que_no_es_pdf_ni_zip():
    with pytest.raises(ArchivoInvalidoError, match="no es un PDF ni un ZIP"):
        pdfs_del_archivo("foto.jpg", b"\xff\xd8\xff imagen")


def test_zip_sin_pdfs():
    with pytest.raises(ArchivoInvalidoError, match="no contiene PDFs"):
        pdfs_del_archivo("vacio.zip", hacer_zip({"leeme.txt": b"hola"}))


def test_zip_danado(crear_pdf):
    comprimido = hacer_zip({"estado.pdf": crear_pdf("Estado")})

    with pytest.raises(ArchivoInvalidoError, match="dañado"):
        pdfs_del_archivo("roto.zip", comprimido[:-30])


def test_zip_con_demasiados_pdfs(monkeypatch, crear_pdf):
    monkeypatch.setattr(archivos, "MAX_PDFS_POR_ZIP", 2)
    comprimido = hacer_zip({f"{n}.pdf": crear_pdf(str(n)) for n in range(3)})

    with pytest.raises(ArchivoInvalidoError, match="más de 2 PDFs"):
        pdfs_del_archivo("muchos.zip", comprimido)


def test_pdf_demasiado_grande_dentro_del_zip(monkeypatch, crear_pdf):
    monkeypatch.setattr(archivos, "TAMANO_MAXIMO", 100)
    comprimido = hacer_zip({"grande.pdf": crear_pdf("Texto largo " * 50)})

    with pytest.raises(ArchivoInvalidoError, match="grande.pdf pesa más de"):
        pdfs_del_archivo("grande.zip", comprimido)
