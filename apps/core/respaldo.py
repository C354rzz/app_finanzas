"""Respaldo y restauración de todos los datos (RF-DAT-01, RF-DAT-02, RNF-06).

Un respaldo es un ZIP con:
- manifiesto.json: formato, fecha, migraciones aplicadas y registros por modelo;
- datos.json: la base de datos (dumpdata con llaves naturales);
- media/…: los archivos subidos (PDFs importados).
"""

import io
import json
import os
import zipfile
from collections import Counter
from pathlib import Path

from django.conf import settings
from django.core.management import call_command
from django.db import connection, transaction
from django.db.migrations.recorder import MigrationRecorder
from django.utils import timezone

FORMATO = 1
PREFIJO = "finanzas-"
# Tablas que Django vuelve a crear solo o que no son datos del usuario.
EXCLUIR = ["contenttypes", "auth.permission", "sessions", "admin.logentry", "django_q"]


class ErrorRespaldo(Exception):
    """Error con un mensaje para el usuario."""


def migraciones_aplicadas():
    """{app: [migraciones]} aplicadas en la base actual."""
    aplicadas = {}
    for app, nombre in MigrationRecorder(connection).applied_migrations():
        aplicadas.setdefault(app, []).append(nombre)
    return {app: sorted(nombres) for app, nombres in sorted(aplicadas.items())}


def _volcar_base():
    salida = io.StringIO()
    call_command("dumpdata", exclude=EXCLUIR, use_natural_foreign_keys=True, stdout=salida)
    return salida.getvalue()


def _archivos_media():
    raiz = Path(settings.MEDIA_ROOT)
    if not raiz.exists():
        return []
    return sorted(ruta for ruta in raiz.rglob("*") if ruta.is_file())


def crear_respaldo(carpeta=None, *, prefijo=PREFIJO, conservar=None):
    """Escribe el ZIP en la carpeta (por omisión RESPALDOS_DIR) y devuelve su ruta."""
    carpeta = Path(carpeta or settings.RESPALDOS_DIR)
    try:
        carpeta.mkdir(parents=True, exist_ok=True)
    except OSError as error:
        raise ErrorRespaldo(
            f"No se pudo usar la carpeta de respaldos {carpeta}: {error}"
        ) from error
    fecha = timezone.localtime()
    destino = carpeta / f"{prefijo}{fecha:%Y%m%d-%H%M%S}.zip"
    temporal = destino.with_name(destino.name + ".tmp")

    externa = connection.in_atomic_block
    with transaction.atomic():
        if not externa:
            # Una sola fotografía de todas las tablas aunque la app se esté usando.
            with connection.cursor() as cursor:
                cursor.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")
        datos = _volcar_base()
        manifiesto = {
            "formato": FORMATO,
            "creado_en": fecha.isoformat(),
            "migraciones": migraciones_aplicadas(),
            "registros": dict(sorted(Counter(r["model"] for r in json.loads(datos)).items())),
        }

    try:
        with zipfile.ZipFile(temporal, "w", zipfile.ZIP_DEFLATED) as respaldo:
            respaldo.writestr("manifiesto.json", json.dumps(manifiesto, ensure_ascii=False))
            respaldo.writestr("datos.json", datos)
            for archivo in _archivos_media():
                relativa = archivo.relative_to(settings.MEDIA_ROOT).as_posix()
                respaldo.write(archivo, f"media/{relativa}")
        os.replace(temporal, destino)
    except OSError as error:
        temporal.unlink(missing_ok=True)
        raise ErrorRespaldo(f"No se pudo escribir el respaldo en {carpeta}: {error}") from error

    if conservar:
        rotar(carpeta, conservar)
    return destino


def rotar(carpeta, conservar):
    """Deja solo los `conservar` respaldos diarios más recientes (no toca los de seguridad)."""
    diarios = sorted(Path(carpeta).glob(f"{PREFIJO}[0-9]*.zip"))
    borrados = diarios[:-conservar] if conservar > 0 else []
    for viejo in borrados:
        viejo.unlink()
    return borrados
