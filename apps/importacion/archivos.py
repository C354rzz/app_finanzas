"""Archivos subidos (IMP-01): huella, detección de PDF y PDFs dentro de un ZIP."""

import hashlib
import io
import lzma
import zipfile
import zlib
from pathlib import PurePosixPath

from apps.importacion.errores import ArchivoInvalidoError

TAMANO_MAXIMO = 20 * 1024 * 1024
MAX_PDFS_POR_ZIP = 20


def huella(datos):
    return hashlib.sha256(datos).hexdigest()


def es_pdf(datos):
    return b"%PDF-" in datos[:1024]


def es_zip(datos):
    return datos[:4] == b"PK\x03\x04"


def megas():
    return TAMANO_MAXIMO // (1024 * 1024)


def pdfs_del_archivo(nombre, datos):
    """Lista de (nombre, contenido) de los PDFs de un archivo subido: PDF suelto o ZIP."""
    # Primero ZIP: un ZIP sin compresión contiene «%PDF-» al inicio de sus miembros.
    if es_zip(datos):
        return _pdfs_del_zip(datos)
    if es_pdf(datos):
        return [(nombre, datos)]
    raise ArchivoInvalidoError("no es un PDF ni un ZIP")


def _pdfs_del_zip(datos):
    try:
        with zipfile.ZipFile(io.BytesIO(datos)) as comprimido:
            miembros = [
                miembro
                for miembro in comprimido.infolist()
                if not miembro.is_dir()
                and miembro.filename.lower().endswith(".pdf")
                and not miembro.filename.startswith("__MACOSX/")
            ]
            if len(miembros) > MAX_PDFS_POR_ZIP:
                raise ArchivoInvalidoError(f"el ZIP tiene más de {MAX_PDFS_POR_ZIP} PDFs")
            pdfs = []
            for miembro in miembros:
                nombre = PurePosixPath(miembro.filename).name
                with comprimido.open(miembro) as archivo:
                    contenido = archivo.read(TAMANO_MAXIMO + 1)
                if len(contenido) > TAMANO_MAXIMO:
                    raise ArchivoInvalidoError(f"{nombre} pesa más de {megas()} MB")
                if es_pdf(contenido):
                    pdfs.append((nombre, contenido))
    except (
        zipfile.BadZipFile, RuntimeError, NotImplementedError, EOFError, zlib.error,
        lzma.LZMAError,
    ) as error:  # fmt: skip
        raise ArchivoInvalidoError("el ZIP está dañado o protegido con contraseña") from error
    if not pdfs:
        raise ArchivoInvalidoError("el ZIP no contiene PDFs")
    return pdfs
