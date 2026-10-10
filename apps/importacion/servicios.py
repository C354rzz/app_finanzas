"""Servicios de importación: registro, procesamiento (worker) y revisión de propuestas."""

import logging
from dataclasses import dataclass

from django.core.files.base import ContentFile
from django.db.models import Sum
from django.utils import timezone
from django_q.tasks import async_task

from apps.calculos.comun import CERO
from apps.importacion import archivos
from apps.importacion.errores import ErrorImportacion
from apps.importacion.models import Documento

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Rechazo:
    nombre: str
    motivo: str


def registrar_archivos(hogar, usuario, subidos, cuenta=None):
    """IMP-01/02: guarda cada PDF (o los PDFs de un ZIP) y lo encola."""
    documentos, rechazos = [], []
    for subido in subidos:
        if subido.size > archivos.TAMANO_MAXIMO:
            rechazos.append(Rechazo(subido.name, f"pesa más de {archivos.megas()} MB"))
            continue
        try:
            pdfs = archivos.pdfs_del_archivo(subido.name, subido.read())
        except ErrorImportacion as error:
            rechazos.append(Rechazo(subido.name, str(error)))
            continue
        for nombre, contenido in pdfs:
            huella = archivos.huella(contenido)
            previo = Documento.objects.del_hogar(hogar).filter(sha256=huella).first()
            if previo:
                fecha = timezone.localtime(previo.creado_en)
                rechazos.append(Rechazo(nombre, f"ya se importó el {fecha:%d/%m/%Y}"))
                continue
            documentos.append(_registrar_pdf(hogar, usuario, nombre, contenido, huella, cuenta))
    return documentos, rechazos


def _registrar_pdf(hogar, usuario, nombre, contenido, huella, cuenta):
    documento = Documento(
        hogar=hogar, nombre_original=nombre[:255], sha256=huella, cuenta=cuenta, subido_por=usuario
    )
    documento.archivo.save(f"{huella}.pdf", ContentFile(contenido), save=False)
    documento.save()
    encolar_procesamiento(documento)
    return documento


def encolar_procesamiento(documento):
    async_task("apps.importacion.tareas.procesar", documento.pk)


def costo_del_mes(hogar, hoy=None):
    """IMP-13: costo de IA acumulado en el mes (US$)."""
    hoy = hoy or timezone.localdate()
    total = (
        Documento.objects.del_hogar(hogar)
        .filter(creado_en__year=hoy.year, creado_en__month=hoy.month)
        .aggregate(total=Sum("costo_estimado_usd"))["total"]
    )
    return total or CERO


def reintentar(documento):
    documento.estado = Documento.Estado.SUBIDO
    documento.error = ""
    documento.save(update_fields=["estado", "error", "actualizado_en"])
    encolar_procesamiento(documento)


def eliminar_documento(documento):
    """Borra el PDF y el documento; los movimientos ya aceptados se conservan."""
    documento.archivo.delete(save=False)
    documento.delete()
