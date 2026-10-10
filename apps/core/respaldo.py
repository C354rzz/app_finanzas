"""Respaldo y restauración de todos los datos (RF-DAT-01, RF-DAT-02, RNF-06).

Un respaldo es un ZIP con:
- manifiesto.json: formato, fecha, migraciones aplicadas y registros por modelo;
- datos.json: la base de datos (dumpdata con llaves naturales);
- media/…: los archivos subidos (PDFs importados).
"""

import io
import json
import os
import tempfile
import zipfile
import zlib
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.core.management import call_command
from django.core.serializers.base import DeserializationError
from django.db import DatabaseError, connection, transaction
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


@dataclass(frozen=True)
class Restauracion:
    registros: int
    archivos: int
    seguridad: Path | None


def _ruta_permitida(nombre):
    r"""Solo rutas relativas dentro de media/: sin «//», «.», «..», «\» ni unidades («C:»)."""
    if not nombre.startswith("media/") or "\\" in nombre:
        return False
    partes = nombre.removeprefix("media/").rstrip("/").split("/")
    return all(parte not in ("", ".", "..") for parte in partes) and ":" not in partes[0]


def leer_respaldo(ruta):
    """Valida el ZIP y devuelve (manifiesto, datos_json, archivos) sin tocar nada."""
    try:
        respaldo = zipfile.ZipFile(ruta)
    except (OSError, zipfile.BadZipFile) as error:
        raise ErrorRespaldo(f"No se pudo abrir el respaldo: {error}") from error
    with respaldo:
        nombres = respaldo.namelist()
        if "manifiesto.json" not in nombres or "datos.json" not in nombres:
            raise ErrorRespaldo(
                "El archivo no es un respaldo de Finanzas (le falta manifiesto.json o datos.json)."
            )
        medios = [n for n in nombres if n not in ("manifiesto.json", "datos.json")]
        for nombre in medios:
            if not _ruta_permitida(nombre):
                raise ErrorRespaldo(f"El respaldo contiene una ruta no permitida: {nombre}")
        try:
            manifiesto = json.loads(respaldo.read("manifiesto.json"))
            datos = respaldo.read("datos.json").decode("utf-8")
            registros = json.loads(datos)
            archivos = {
                n.removeprefix("media/"): respaldo.read(n) for n in medios if not n.endswith("/")
            }
        except (zipfile.BadZipFile, ValueError, zlib.error, EOFError) as error:
            raise ErrorRespaldo("El respaldo está dañado.") from error
    migraciones = manifiesto.get("migraciones", {}) if isinstance(manifiesto, dict) else None
    if (
        not isinstance(manifiesto, dict)
        or manifiesto.get("formato") != FORMATO
        or not isinstance(migraciones, dict)
        or not all(isinstance(nombres, list) for nombres in migraciones.values())
    ):
        raise ErrorRespaldo("El respaldo tiene un formato desconocido.")
    if not isinstance(registros, list):
        raise ErrorRespaldo("El respaldo está dañado.")
    return manifiesto, datos, archivos


def _validar_migraciones(manifiesto):
    actuales = migraciones_aplicadas()
    faltantes = [
        f"{app}.{nombre}"
        for app, nombres in (manifiesto.get("migraciones") or {}).items()
        for nombre in nombres
        if nombre not in actuales.get(app, [])
    ]
    if faltantes:
        raise ErrorRespaldo(
            "El respaldo es de una versión más nueva de la app (faltan migraciones: "
            + ", ".join(faltantes[:5])
            + "). Actualiza el código antes de restaurar."
        )


def _escribir_media(archivos):
    raiz = Path(settings.MEDIA_ROOT).resolve()
    for relativa, contenido in archivos.items():
        destino = (raiz / relativa).resolve()
        if not destino.is_relative_to(raiz):  # defensa adicional; leer_respaldo ya lo validó
            raise OSError(f"ruta fuera de media: {relativa}")
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_bytes(contenido)


def restaurar_respaldo(ruta):
    """Reemplaza TODOS los datos por los del respaldo. Si algo falla, la base queda igual."""
    manifiesto, datos, archivos = leer_respaldo(ruta)
    _validar_migraciones(manifiesto)
    seguridad = None
    if get_user_model().objects.exists():
        seguridad = crear_respaldo(prefijo=f"{PREFIJO}antes-de-restaurar-")
    with tempfile.TemporaryDirectory() as carpeta:
        fixture = Path(carpeta) / "datos.json"  # loaddata reconoce el formato por la extensión
        fixture.write_text(datos, encoding="utf-8")
        try:
            with transaction.atomic():
                call_command("flush", interactive=False, verbosity=0)
                call_command("loaddata", str(fixture), verbosity=0)
        except (DatabaseError, DeserializationError, ValueError) as error:
            raise ErrorRespaldo(
                f"No se pudo cargar el respaldo; no se cambió nada. Detalle: {error}"
            ) from error
    ContentType.objects.clear_cache()  # flush recreó los tipos de contenido con otros ids
    try:
        _escribir_media(archivos)
    except OSError as error:
        anterior = (
            f" Tus datos anteriores están en el respaldo de seguridad {seguridad.name}."
            if seguridad
            else ""
        )
        raise ErrorRespaldo(
            f"Se restauró la base de datos, pero no se pudieron escribir los archivos (PDFs): "
            f"{error}. Libera espacio o revisa permisos y vuelve a restaurar.{anterior}"
        ) from error
    return Restauracion(
        registros=len(json.loads(datos)), archivos=len(archivos), seguridad=seguridad
    )
