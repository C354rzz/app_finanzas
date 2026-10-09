from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.catalogos.servicios import sembrar_catalogos
from apps.core.models import Membresia
from apps.core.servicios import crear_hogar


class Command(BaseCommand):
    help = "Crea un hogar para un usuario existente y siembra los catálogos iniciales."

    def add_arguments(self, parser):
        parser.add_argument("--nombre", required=True, help="Nombre del hogar")
        parser.add_argument("--email", required=True, help="Email del usuario administrador")

    @transaction.atomic
    def handle(self, *args, nombre, email, **options):
        Usuario = get_user_model()
        try:
            usuario = Usuario.objects.get_by_natural_key(email)
        except Usuario.DoesNotExist as error:
            raise CommandError(f"No existe un usuario con email {email}") from error
        if Membresia.objects.filter(usuario=usuario).exists():
            raise CommandError(f"{usuario.email} ya pertenece a un hogar")

        hogar = crear_hogar(nombre, usuario)
        categorias = sembrar_catalogos(hogar)
        self.stdout.write(
            self.style.SUCCESS(f"Hogar '{hogar}' creado con {categorias} categorías.")
        )
