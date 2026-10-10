"""Regresiones de la revisión final del plan 4."""

import io
import json
import zipfile
from datetime import date, timedelta
from decimal import Decimal as D

import pytest
from django.core.files.base import ContentFile
from django.utils import timezone

from apps.importacion import servicios
from apps.importacion.archivos import huella, pdfs_del_archivo
from apps.importacion.errores import ArchivoInvalidoError
from apps.importacion.extractor import ExtractorClaude, Uso, interpretar
from apps.importacion.models import Documento, MovimientoPropuesto
from apps.importacion.texto import proteger_datos
from apps.movimientos.models import Movimiento

pytestmark = pytest.mark.django_db


def documento_con_pdf(hogar, crear_pdf, **campos):
    datos = crear_pdf("Estado de cuenta Banco Demo con texto suficiente")
    documento = Documento(hogar=hogar, nombre_original="estado.pdf", sha256=huella(datos), **campos)
    documento.archivo.save("x.pdf", ContentFile(datos), save=False)
    documento.save()
    return documento


def test_zip_con_datos_comprimidos_danados(crear_pdf):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as comprimido:
        comprimido.writestr("estado.pdf", crear_pdf("Texto " * 200))
    datos = bytearray(buffer.getvalue())
    for posicion in range(60, 90):
        datos[posicion] ^= 0xFF

    with pytest.raises(ArchivoInvalidoError, match="dañado"):
        pdfs_del_archivo("roto.zip", bytes(datos))


def test_cliente_de_la_ia_con_tiempo_limite(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-prueba")

    cliente = ExtractorClaude().cliente

    assert cliente.timeout == 240
    assert cliente.max_retries == 2


def test_documento_atascado_en_procesando_pasa_a_error(cliente, hogar):
    atascado = Documento.objects.create(
        hogar=hogar, nombre_original="a.pdf", sha256="a" * 64, estado=Documento.Estado.PROCESANDO
    )
    Documento.objects.filter(pk=atascado.pk).update(
        actualizado_en=timezone.now() - timedelta(hours=1)
    )

    contenido = cliente.get("/importar/documentos/").content.decode()

    atascado.refresh_from_db()
    assert atascado.estado == Documento.Estado.ERROR
    assert "interrumpió" in atascado.error
    assert 'hx-trigger="every 3s"' not in contenido


def test_borrar_durante_el_procesamiento_no_lo_revive(hogar, crear_pdf, monkeypatch):
    documento = documento_con_pdf(hogar, crear_pdf)
    datos = {
        "tipo_documento": "estado_cuenta", "emisor": "Banco Demo", "periodo_inicio": "",
        "periodo_fin": "", "ultimos_digitos_cuenta": "", "saldo_al_corte": "", "movimientos": [],
    }  # fmt: skip

    class ExtractorQueBorra:
        def extraer(self, texto, catalogos):
            Documento.objects.filter(pk=documento.pk).delete()
            return interpretar(json.dumps(datos), Uso("claude-opus-5-5", 1, 1, D("0")))

    monkeypatch.setattr(servicios, "obtener_extractor", ExtractorQueBorra)

    servicios.procesar_documento(documento.pk)

    assert not Documento.objects.filter(pk=documento.pk).exists()


def test_no_se_elimina_un_documento_en_proceso(cliente, hogar):
    en_proceso = Documento.objects.create(
        hogar=hogar, nombre_original="a.pdf", sha256="a" * 64, estado=Documento.Estado.PROCESANDO
    )

    cliente.post(f"/importar/{en_proceso.pk}/eliminar/")

    assert Documento.objects.filter(pk=en_proceso.pk).exists()


def test_ocultar_datos_pegados_a_su_etiqueta():
    texto = (
        "RFCXAXX010101000 CURPXEXX010101HNEXXXA4 No.Tarjeta4152313412345678 "
        "CLABE012180001234567890 rfc xaxx010101000"
    )

    protegido = proteger_datos(texto)

    for dato in ("XAXX010101000", "XEXX010101HNEXXXA4", "4152313412345678",
                 "012180001234567890", "xaxx010101000"):  # fmt: skip
        assert dato not in protegido
    assert "****5678" in protegido
    assert "****7890" in protegido


def test_no_se_actualiza_el_saldo_con_pagos_pendientes(catalogo, hogar):
    documento = Documento.objects.create(
        hogar=hogar, nombre_original="tarjeta.pdf", sha256="a" * 64, cuenta=catalogo.tarjeta,
        saldo_al_corte=D("7000"), periodo_fin=date(2026, 10, 5),
    )  # fmt: skip
    MovimientoPropuesto.objects.create(
        hogar=hogar,
        documento=documento,
        fecha=date(2026, 9, 20),
        descripcion_original="SU PAGO GRACIAS",
        descripcion="SU PAGO GRACIAS",
        monto=D("2000"),
        tipo=Movimiento.Tipo.PAGO_DEUDA,
        cuenta_destino=catalogo.tarjeta,
    )

    assert servicios.actualizar_saldo(documento) is False

    catalogo.tarjeta.refresh_from_db()
    assert catalogo.tarjeta.saldo_actual == D("6839.01")


def test_no_se_regresa_a_un_saldo_mas_viejo(catalogo, hogar):
    catalogo.tarjeta.fecha_saldo = date(2026, 11, 5)
    catalogo.tarjeta.save()
    viejo = Documento.objects.create(
        hogar=hogar, nombre_original="viejo.pdf", sha256="a" * 64, cuenta=catalogo.tarjeta,
        saldo_al_corte=D("100"), periodo_fin=date(2026, 10, 5),
    )  # fmt: skip

    assert servicios.actualizar_saldo(viejo) is False

    catalogo.tarjeta.refresh_from_db()
    assert catalogo.tarjeta.saldo_actual == D("6839.01")
