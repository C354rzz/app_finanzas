from django.shortcuts import redirect
from django.utils import timezone

from apps.core.acceso import requiere_hogar


@requiere_hogar
def inicio(request):
    hoy = timezone.localdate()
    return redirect("tablero:mes", hoy.year, hoy.month)
