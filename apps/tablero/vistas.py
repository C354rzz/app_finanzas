from django.http import Http404
from django.shortcuts import render

from apps.core.acceso import requiere_hogar
from apps.core.fechas import mes_anterior, mes_siguiente, nombre_mes, validar_mes
from apps.tablero.formularios import FormularioFiltrosTablero
from apps.tablero.servicios import armar_tablero


@requiere_hogar
def del_mes(request, anio, mes):
    try:
        validar_mes(anio, mes)
    except ValueError as error:
        raise Http404 from error
    filtros = FormularioFiltrosTablero(request.GET or None, hogar=request.hogar)
    contexto = {
        "tablero": armar_tablero(request.hogar, anio, mes, **filtros.elegidos()),
        "filtros": filtros,
        "titulo": nombre_mes(anio, mes),
        "anterior": mes_anterior(anio, mes),
        "siguiente": mes_siguiente(anio, mes),
        "consulta": request.GET.urlencode(),
    }
    return render(request, "tablero/mes.html", contexto)
