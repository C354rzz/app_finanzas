from django.core.management.base import BaseCommand, CommandError

from apps.core.respaldo import ErrorRespaldo, crear_respaldo


class Command(BaseCommand):
    help = "Respalda la base de datos y los archivos subidos en un ZIP (RF-DAT-01)."

    def add_arguments(self, parser):
        parser.add_argument("--carpeta", help="Carpeta destino (por omisión RESPALDOS_DIR).")
        parser.add_argument(
            "--conservar",
            type=int,
            default=30,
            help="Cuántos respaldos diarios conservar (0 = todos).",
        )

    def handle(self, *args, carpeta=None, conservar=30, **opciones):
        try:
            destino = crear_respaldo(carpeta, conservar=conservar)
        except ErrorRespaldo as error:
            raise CommandError(str(error)) from error
        kb = destino.stat().st_size // 1024
        self.stdout.write(self.style.SUCCESS(f"Respaldo creado: {destino.name} ({kb} KB)"))
