from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.core.acceso import requiere_hogar
from apps.core.htmx import datos_actualizados, es_htmx, responder_formulario
from apps.planeacion.formularios import FormularioMeta
from apps.planeacion.models import MetaAhorro
from apps.planeacion.servicios import resumir_metas
from apps.presupuesto.servicios import obtener_presupuesto_mes, resumen_mes


def _mes_actual(hogar):
    hoy = timezone.localdate()
    return resumen_mes(obtener_presupuesto_mes(hogar, hoy.year, hoy.month))


def _editar(request, Formulario, instancia, destino, titulo):
    datos = request.POST if request.method == "POST" else None
    formulario = Formulario(datos, instance=instancia, hogar=request.hogar)
    if datos is not None and formulario.is_valid():
        formulario.save()
        return datos_actualizados() if es_htmx(request) else redirect(destino)
    contexto = {"formulario": formulario, "titulo": titulo, "accion": request.path}
    return responder_formulario(request, contexto)


def _eliminar(request, modelo, pk, destino):
    get_object_or_404(modelo.objects.del_hogar(request.hogar), pk=pk).delete()
    return datos_actualizados() if es_htmx(request) else redirect(destino)


@requiere_hogar
def metas(request):
    resumen = _mes_actual(request.hogar)
    contexto = {
        "metas": resumir_metas(request.hogar, resumen),
        "resumen": resumen,
        "pausadas": MetaAhorro.objects.del_hogar(request.hogar).filter(activa=False),
    }
    return render(request, "planeacion/metas.html", contexto)


@requiere_hogar
def meta_nueva(request):
    return _editar(request, FormularioMeta, None, "planeacion:metas", "Nueva meta de ahorro")


@requiere_hogar
def meta_editar(request, pk):
    meta = get_object_or_404(MetaAhorro.objects.del_hogar(request.hogar), pk=pk)
    return _editar(request, FormularioMeta, meta, "planeacion:metas", "Editar meta de ahorro")


@requiere_hogar
@require_POST
def meta_eliminar(request, pk):
    return _eliminar(request, MetaAhorro, pk, "planeacion:metas")
