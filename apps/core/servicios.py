from django.db import transaction

from apps.core.models import Hogar, Membresia


@transaction.atomic
def crear_hogar(nombre, usuario, rol=Membresia.Rol.ADMIN):
    """Crea un hogar y da al usuario acceso con el rol indicado."""
    hogar = Hogar.objects.create(nombre=nombre)
    Membresia.objects.create(hogar=hogar, usuario=usuario, rol=rol)
    return hogar
