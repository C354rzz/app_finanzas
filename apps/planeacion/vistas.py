from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.core.acceso import requiere_hogar
from apps.core.htmx import datos_actualizados, es_htmx, responder_formulario
from apps.planeacion.formularios import FormularioActivo, FormularioMeta
from apps.planeacion.models import Activo, MetaAhorro
from apps.planeacion.servicios import calcular_patrimonio, resumir_metas, vista_deudas
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


@requiere_hogar
def deudas(request):
    hoy = timezone.localdate()
    vista = vista_deudas(request.hogar, hoy.year, hoy.month)
    contexto = {
        "deudas": vista,
        "total_deudas": vista.resumen.total_tarjetas + vista.resumen.total_creditos,
    }
    return render(request, "planeacion/deudas.html", contexto)


@requiere_hogar
def patrimonio(request):
    contexto = {
        "patrimonio": calcular_patrimonio(request.hogar),
        "no_vigentes": Activo.objects.del_hogar(request.hogar).filter(activo=False),
    }
    return render(request, "planeacion/patrimonio.html", contexto)


@requiere_hogar
def activo_nuevo(request):
    return _editar(request, FormularioActivo, None, "planeacion:patrimonio", "Nuevo activo")


@requiere_hogar
def activo_editar(request, pk):
    activo = get_object_or_404(Activo.objects.del_hogar(request.hogar), pk=pk)
    return _editar(request, FormularioActivo, activo, "planeacion:patrimonio", "Editar activo")


@requiere_hogar
@require_POST
def activo_eliminar(request, pk):
    return _eliminar(request, Activo, pk, "planeacion:patrimonio")
