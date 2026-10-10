"""Errores de importación. Su mensaje se muestra tal cual al usuario."""


class ErrorImportacion(Exception):
    pass


class ArchivoInvalidoError(ErrorImportacion):
    pass


class PdfInvalidoError(ErrorImportacion):
    pass


class PdfProtegidoError(ErrorImportacion):
    pass


class SinTextoError(ErrorImportacion):
    pass


class ErrorExtraccion(ErrorImportacion):
    pass
