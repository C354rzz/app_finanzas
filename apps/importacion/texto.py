"""Texto de un PDF (IMP-04) y protección de datos antes de enviarlo a la IA (RNF-03)."""

import io
import re

from pypdf import PdfReader

from apps.importacion.errores import (
    ErrorImportacion,
    PdfInvalidoError,
    PdfProtegidoError,
    SinTextoError,
)

MINIMO_CARACTERES = 20

# Sin \b al inicio: pypdf suele pegar la etiqueta al dato («RFCXAXX010101000»).
_CURP = re.compile(r"[A-Z][AEIOUX][A-Z]{2}\d{6}[HM][A-Z]{5}[A-Z0-9]\d(?![A-Z0-9])", re.IGNORECASE)
_RFC = re.compile(r"[A-ZÑ&]{3,4}\d{6}[A-Z0-9]{3}(?![A-Z0-9])", re.IGNORECASE)
_TARJETA = re.compile(r"(?<!\d)(?:\d{4}[ -]){3}(\d{4})(?!\d)")
_NUMERO_LARGO = re.compile(r"(?<!\d)\d{6,}(\d{4})(?!\d)")


def extraer_texto(datos):
    """Devuelve (texto con un encabezado por página, número de páginas)."""
    try:
        lector = PdfReader(io.BytesIO(datos))
        if lector.is_encrypted and not lector.decrypt(""):
            raise PdfProtegidoError(
                "El PDF está protegido con contraseña; quítasela y vuelve a subirlo."
            )
        if not lector.pages:
            raise PdfInvalidoError("El PDF está dañado o no tiene páginas.")
        paginas = [(pagina.extract_text() or "").strip() for pagina in lector.pages]
    except ErrorImportacion:
        raise
    except Exception as error:  # pypdf lanza distintos errores ante PDFs dañados
        raise PdfInvalidoError("El PDF está dañado o no se puede leer.") from error
    if sum(len(texto) for texto in paginas) < MINIMO_CARACTERES:
        raise SinTextoError(
            "El PDF no tiene texto (parece escaneado) y requiere OCR, que aún no está disponible."
        )
    texto = "\n\n".join(f"--- Página {n} ---\n{t}" for n, t in enumerate(paginas, start=1))
    return texto, len(paginas)


def proteger_datos(texto):
    """Oculta RFC, CURP y números largos (tarjeta, CLABE, NSS, servicio) dejando 4 dígitos."""
    texto = _CURP.sub("[CURP]", texto)
    texto = _RFC.sub("[RFC]", texto)
    texto = _TARJETA.sub(lambda m: f"****{m.group(1)}", texto)
    return _NUMERO_LARGO.sub(lambda m: f"****{m.group(1)}", texto)
