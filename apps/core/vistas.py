from django.shortcuts import render

from apps.core.acceso import requiere_hogar


@requiere_hogar
def inicio(request):
    return render(request, "core/inicio.html")
