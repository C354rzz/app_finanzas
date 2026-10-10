from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.core.respaldo import ErrorRespaldo, restaurar_respaldo


class Command(BaseCommand):
    help = "Reemplaza TODOS los datos por los de un respaldo (RF-DAT-02)."

    def add_arguments(self, parser):
        parser.add_argument("archivo", help="Ruta del ZIP o su nombre dentro de RESPALDOS_DIR.")
        parser.add_argument(
            "--confirmar",
            action="store_true",
            help="Confirma que se reemplazarán todos los datos actuales.",
        )

    def handle(self, *args, archivo, confirmar=False, **opciones):
        ruta = Path(archivo)
        if not ruta.exists():
            ruta = Path(settings.RESPALDOS_DIR) / archivo
        if not ruta.is_file():
            raise CommandError(f"No existe el respaldo {archivo}.")
        if not confirmar:
            raise CommandError(
                "Esto reemplaza TODOS los datos actuales por los del respaldo. "
                "Repite el comando con --confirmar."
            )
        try:
            resultado = restaurar_respaldo(ruta)
        except ErrorRespaldo as error:
            raise CommandError(str(error)) from error
        if resultado.seguridad:
            self.stdout.write(f"Respaldo de los datos anteriores: {resultado.seguridad.name}")
        self.stdout.write(
            self.style.SUCCESS(
                f"Restaurado: {resultado.registros} registros y {resultado.archivos} archivos."
            )
        )
