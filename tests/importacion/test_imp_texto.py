import io

import pytest
from pypdf import PdfWriter

from apps.importacion.errores import PdfInvalidoError, PdfProtegidoError, SinTextoError
from apps.importacion.texto import extraer_texto, proteger_datos


def cifrar(datos, clave_usuario):
    escritor = PdfWriter(clone_from=io.BytesIO(datos))
    escritor.encrypt(user_password=clave_usuario, owner_password="duenio", algorithm="AES-256")
    salida = io.BytesIO()
    escritor.write(salida)
    return salida.getvalue()


def test_extrae_el_texto_por_pagina(crear_pdf):
    texto, paginas = extraer_texto(
        crear_pdf("BANCO DEMO\nCompra OXXO 85.50", "Pago recibido 2000.00")
    )

    assert paginas == 2
    assert "Compra OXXO 85.50" in texto
    assert "--- Página 2 ---" in texto
    assert "Pago recibido 2000.00" in texto


def test_pdf_sin_texto_requiere_ocr(crear_pdf):
    with pytest.raises(SinTextoError, match="OCR"):
        extraer_texto(crear_pdf("", ""))


def test_pdf_danado():
    with pytest.raises(PdfInvalidoError):
        extraer_texto(b"%PDF-1.4 esto no es un pdf completo")


def test_pdf_protegido_con_contrasena(crear_pdf):
    with pytest.raises(PdfProtegidoError, match="contraseña"):
        extraer_texto(cifrar(crear_pdf("Estado de cuenta secreto"), "clave"))


def test_pdf_cifrado_sin_contrasena_de_apertura_se_lee(crear_pdf):
    texto, _ = extraer_texto(cifrar(crear_pdf("Estado de cuenta Banco Demo"), ""))

    assert "Estado de cuenta Banco Demo" in texto


def test_proteger_datos_personales():
    texto = (
        "RFC XAXX010101000 CURP XEXX010101HNEXXXA4 tarjeta 4152 3131 2345 6789 "
        "CLABE 012180001234567891 servicio 123456789012 monto 1,234.56 fecha 2026-10-05"
    )

    protegido = proteger_datos(texto)

    for dato in ("XAXX010101000", "XEXX010101HNEXXXA4", "4152", "012180001234567891",
                 "123456789012"):  # fmt: skip
        assert dato not in protegido
    for marca in ("[RFC]", "[CURP]", "****6789", "****7891", "****9012", "1,234.56",
                  "2026-10-05"):  # fmt: skip
        assert marca in protegido
