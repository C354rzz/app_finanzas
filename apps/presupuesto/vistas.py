from django.contrib import messages
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.calculos.comun import redondear
from apps.core.acceso import requiere_hogar
from apps.core.fechas import mes_anterior, mes_siguiente, nombre_mes
from apps.core.htmx import datos_actualizados, es_htmx, responder_formulario
from apps.presupuesto import mensajes
from apps.presupuesto.formularios import RENGLONES, FormularioPorcentaje
from apps.presupuesto.models import PresupuestoMes
from apps.presupuesto.servicios import (
    obtener_plantilla,
    obtener_presupuesto_mes,
    resincronizar_mes,
    resumen_mes,
    resumen_plantilla,
)


@requiere_hogar
def inicio(request):
    hoy = timezone.localdate()
    return redirect("presupuesto:mes", hoy.year, hoy.month)


@requiere_hogar
def plantilla(request):
    contenedor = obtener_plantilla(request.hogar)
    contexto = _contexto(contenedor, resumen_plantilla(contenedor), "plantilla", "Plantilla")
    contexto["urls"] = {
        "porcentaje": reverse("presupuesto:porcentaje_plantilla"),
        "nuevo_ingreso": reverse("presupuesto:nuevo_plantilla", args=["ingreso"]),
        "nuevo_gasto": reverse("presupuesto:nuevo_plantilla", args=["gasto"]),
    }
    return render(request, "presupuesto/pagina.html", contexto)


@requiere_hogar
def del_mes(request, anio, mes):
    contenedor = _presupuesto_mes(request, anio, mes)
    contexto = _contexto(contenedor, resumen_mes(contenedor), "mes", nombre_mes(anio, mes))
    contexto["anterior"] = mes_anterior(anio, mes)
    contexto["siguiente"] = mes_siguiente(anio, mes)
    contexto["urls"] = {
        "porcentaje": reverse("presupuesto:porcentaje_mes", args=[anio, mes]),
        "nuevo_ingreso": reverse("presupuesto:nuevo_mes", args=[anio, mes, "ingreso"]),
        "nuevo_gasto": reverse("presupuesto:nuevo_mes", args=[anio, mes, "gasto"]),
        "resincronizar": reverse("presupuesto:resincronizar", args=[anio, mes]),
    }
    return render(request, "presupuesto/pagina.html", contexto)


@requiere_hogar
def renglon_nuevo(request, ambito, clase, anio=None, mes=None):
    Formulario = _formulario_de(ambito, clase)
    return _editar_renglon(request, Formulario, _contenedor(request, ambito, anio, mes), None)


@requiere_hogar
def renglon_editar(request, ambito, clase, pk):
    Formulario = _formulario_de(ambito, clase)
    renglon = get_object_or_404(Formulario._meta.model.objects.del_hogar(request.hogar), pk=pk)
    contenedor = getattr(renglon, Formulario.contenedor_campo)
    return _editar_renglon(request, Formulario, contenedor, renglon)


@requiere_hogar
@require_POST
def renglon_eliminar(request, ambito, clase, pk):
    Formulario = _formulario_de(ambito, clase)
    renglon = get_object_or_404(Formulario._meta.model.objects.del_hogar(request.hogar), pk=pk)
    destino = _url_de(getattr(renglon, Formulario.contenedor_campo))
    renglon.delete()
    return datos_actualizados() if es_htmx(request) else redirect(destino)


@requiere_hogar
@require_POST
def porcentaje(request, ambito, anio=None, mes=None):
    contenedor = _contenedor(request, ambito, anio, mes)
    formulario = FormularioPorcentaje(request.POST)
    if formulario.is_valid():
        contenedor.porcentaje_ahorro = formulario.fraccion()
        contenedor.save(update_fields=["porcentaje_ahorro", "actualizado_en"])
        messages.success(request, "Porcentaje de ahorro actualizado.")
    else:
        messages.error(request, "El porcentaje de ahorro debe estar entre 0 y 100.")
    return redirect(_url_de(contenedor))


@requiere_hogar
@require_POST
def resincronizar(request, anio, mes):
    resincronizar_mes(_presupuesto_mes(request, anio, mes))
    messages.success(request, "El presupuesto del mes se re-sincronizó con la plantilla.")
    return redirect("presupuesto:mes", anio, mes)


def _presupuesto_mes(request, anio, mes):
    try:
        return obtener_presupuesto_mes(request.hogar, anio, mes)
    except ValueError as error:
        raise Http404 from error


def _contenedor(request, ambito, anio, mes):
    if ambito == "plantilla":
        return obtener_plantilla(request.hogar)
    return _presupuesto_mes(request, anio, mes)


def _url_de(contenedor):
    if isinstance(contenedor, PresupuestoMes):
        return reverse("presupuesto:mes", args=[contenedor.anio, contenedor.mes])
    return reverse("presupuesto:plantilla")


def _formulario_de(ambito, clase):
    Formulario = RENGLONES.get((ambito, clase))
    if Formulario is None:
        raise Http404("Renglón desconocido")
    return Formulario


def _editar_renglon(request, Formulario, contenedor, renglon):
    datos = request.POST if request.method == "POST" else None
    formulario = Formulario(datos, instance=renglon, contenedor=contenedor, hogar=request.hogar)
    if datos is not None and formulario.is_valid():
        formulario.save()
        return datos_actualizados() if es_htmx(request) else redirect(_url_de(contenedor))
    accion = "Editar" if renglon else "Agregar"
    titulo = f"{accion} {Formulario._meta.model._meta.verbose_name}"
    return responder_formulario(
        request, {"formulario": formulario, "titulo": titulo, "accion": request.path}
    )


def _contexto(contenedor, resumen, ambito, titulo):
    return {
        "ambito": ambito,
        "titulo": titulo,
        "resumen": resumen,
        "ingresos": contenedor.ingresos.select_related("persona"),
        "gastos": contenedor.gastos.select_related("concepto__categoria", "concepto__domicilio"),
        "mensajes": {
            "ahorro": mensajes.mensaje_ahorro(contenedor.porcentaje_ahorro),
            "disponible": mensajes.mensaje_disponible(resumen.disponible, resumen.meta_ahorro),
            "recorte": mensajes.mensaje_recorte(resumen.recorte_necesario),
        },
        "formulario_porcentaje": FormularioPorcentaje(
            initial={"porcentaje": redondear(contenedor.porcentaje_ahorro * 100)}
        ),
    }
