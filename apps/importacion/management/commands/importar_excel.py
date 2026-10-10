from django.core.management.base import BaseCommand, CommandError

from apps.core.models import Membresia
from apps.importacion.excel import SECCIONES, ErrorExcel, importar_excel


class Command(BaseCommand):
    help = (
        "Importación inicial desde el Excel del planeador (RF-ACC-04). "
        "Por omisión solo simula; usa --aplicar para guardar."
    )

    def add_arguments(self, parser):
        parser.add_argument("archivo", help="Ruta del .xlsx dentro del contenedor.")
        parser.add_argument("--email", help="Email del dueño del hogar (si hay más de uno).")
        parser.add_argument("--aplicar", action="store_true", help="Guarda los datos.")
        parser.add_argument(
            "--detalle", action="store_true", help="Muestra los avisos (pueden incluir nombres)."
        )

    def handle(self, *args, archivo, email=None, aplicar=False, detalle=False, **opciones):
        hogar = self._hogar(email)
        try:
            resumen = importar_excel(archivo, hogar, aplicar=aplicar)
        except ErrorExcel as error:
            raise CommandError(str(error)) from error
        if not aplicar:
            self.stdout.write(
                self.style.WARNING("Simulación: no se guardó nada. Usa --aplicar para importar.")
            )
        self.stdout.write(f"{'Sección':<26}{'nuevos':>8}{'ya existían':>13}")
        for seccion in SECCIONES:
            creados, existentes = resumen.creados[seccion], resumen.existentes[seccion]
            self.stdout.write(f"{seccion:<26}{creados:>8}{existentes:>13}")
        pista = " (usa --detalle para verlos)" if resumen.avisos and not detalle else ""
        self.stdout.write(f"Avisos: {len(resumen.avisos)}{pista}")
        if detalle:
            for aviso in resumen.avisos:
                self.stdout.write(f"- {aviso}")

    def _hogar(self, email):
        membresias = Membresia.objects.select_related("hogar").order_by("creado_en", "id")
        if email:
            membresia = membresias.filter(usuario__email__iexact=email).first()
            if membresia is None:
                raise CommandError(f"No hay un hogar para {email}.")
            return membresia.hogar
        hogares = {membresia.hogar_id: membresia.hogar for membresia in membresias}
        if len(hogares) != 1:
            raise CommandError("Indica --email: hay más de un hogar, o ninguno.")
        return next(iter(hogares.values()))
