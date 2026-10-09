from django.contrib import messages
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render

from apps.catalogos.models import Concepto
from apps.core.acceso import requiere_hogar
from apps.core.htmx import datos_actualizados, es_htmx
from apps.movimientos.formularios import FORMULARIOS, FormularioGasto
from apps.movimientos.models import Movimiento
from apps.movimientos.servicios import guardar_movimiento, valores_sugeridos


@requiere_hogar
def capturar(request, tipo):
    Formulario = FORMULARIOS.get(tipo)
    if Formulario is None:
        raise Http404("Tipo de movimiento desconocido")
    datos = request.POST if request.method == "POST" else None
    formulario = Formulario(datos, hogar=request.hogar)
    if datos is not None and formulario.is_valid():
        movimiento = guardar_movimiento(formulario.save(commit=False), usuario=request.user)
        return _guardado(request, movimiento)
    return _formulario(request, formulario, tipo, Movimiento.Tipo.choices, "Registrar")


@requiere_hogar
def sugeridos(request):
    """Campos que precarga el concepto elegido (se pide al cambiar el concepto)."""
    valor = request.GET.get("concepto", "")
    iniciales = {}
    if valor.isdigit():
        concepto = get_object_or_404(Concepto.objects.del_hogar(request.hogar), pk=valor)
        iniciales = valores_sugeridos(concepto)
    formulario = FormularioGasto(hogar=request.hogar, initial=iniciales)
    return render(request, "movimientos/_campos_sugeridos.html", {"formulario": formulario})


def _formulario(request, formulario, tipo, tipos, titulo):
    contexto = {
        "formulario": formulario,
        "tipo": tipo,
        "tipos": tipos,
        "titulo": titulo,
        "accion": request.path,
    }
    plantilla = "movimientos/_captura.html" if es_htmx(request) else "movimientos/captura.html"
    return render(request, plantilla, contexto)


def _guardado(request, movimiento):
    if es_htmx(request):
        return datos_actualizados()
    messages.success(request, "Movimiento guardado.")
    return redirect("inicio")
