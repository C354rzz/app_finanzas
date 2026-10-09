import csv

from django.contrib import messages
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.catalogos.models import Concepto
from apps.core.acceso import requiere_hogar
from apps.core.fechas import mes_anterior, mes_siguiente, nombre_mes, rango_del_anio, rango_del_mes
from apps.core.htmx import datos_actualizados, es_htmx
from apps.movimientos.consultas import movimientos_entre, totales
from apps.movimientos.formularios import FORMULARIOS, FormularioFiltros, FormularioGasto
from apps.movimientos.models import Movimiento
from apps.movimientos.servicios import eliminar_movimiento, guardar_movimiento, valores_sugeridos


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
    return redirect("movimientos:lista", movimiento.fecha.year, movimiento.fecha.month)


ENCABEZADOS_CSV = [
    "fecha", "tipo", "descripción", "categoría", "concepto", "monto", "método de pago",
    "cuenta", "cuenta destino", "persona", "domicilio", "hormiga", "extraordinario",
    "tipo de ingreso",
]  # fmt: skip


@requiere_hogar
def inicio(request):
    hoy = timezone.localdate()
    return redirect("movimientos:lista", hoy.year, hoy.month)


@requiere_hogar
def lista(request, anio, mes):
    try:
        inicio_mes, fin_mes = rango_del_mes(anio, mes)
    except ValueError as error:
        raise Http404 from error
    filtros = FormularioFiltros(request.GET or None, hogar=request.hogar)
    movimientos = movimientos_entre(request.hogar, inicio_mes, fin_mes, filtros.filtros())
    resumen = totales(movimientos)
    contexto = {
        "anio": anio,
        "mes": mes,
        "titulo": nombre_mes(anio, mes),
        "anterior": mes_anterior(anio, mes),
        "siguiente": mes_siguiente(anio, mes),
        "consulta": request.GET.urlencode(),
        "filtros": filtros,
        "movimientos": movimientos,
        "totales": resumen,
        "tablas": [
            ("Gastos por categoría", [(str(c), t) for c, t in resumen.por_categoria]),
            ("Por método de pago", resumen.por_metodo),
            ("Por cuenta", resumen.por_cuenta),
        ],
    }
    return render(request, "movimientos/lista.html", contexto)


@requiere_hogar
def editar(request, pk):
    movimiento = get_object_or_404(Movimiento.objects.del_hogar(request.hogar), pk=pk)
    Formulario = FORMULARIOS[movimiento.tipo]
    datos = request.POST if request.method == "POST" else None
    formulario = Formulario(datos, instance=movimiento, hogar=request.hogar)
    if datos is not None and formulario.is_valid():
        return _guardado(request, guardar_movimiento(formulario.save(commit=False)))
    return _formulario(request, formulario, movimiento.tipo, None, "Editar movimiento")


@requiere_hogar
@require_POST
def eliminar(request, pk):
    movimiento = get_object_or_404(Movimiento.objects.del_hogar(request.hogar), pk=pk)
    eliminar_movimiento(movimiento)
    if es_htmx(request):
        return datos_actualizados()
    messages.success(request, "Movimiento eliminado.")
    return redirect("movimientos:lista", movimiento.fecha.year, movimiento.fecha.month)


@requiere_hogar
def exportar_csv(request, anio, mes=None):
    """RF-MOV-07: movimientos del mes o del año (con los filtros activos) en CSV."""
    try:
        inicio_rango, fin_rango = rango_del_mes(anio, mes) if mes else rango_del_anio(anio)
    except ValueError as error:
        raise Http404 from error
    filtros = FormularioFiltros(request.GET or None, hogar=request.hogar).filtros()
    movimientos = movimientos_entre(request.hogar, inicio_rango, fin_rango, filtros)
    nombre = f"movimientos-{anio}-{mes:02d}.csv" if mes else f"movimientos-{anio}.csv"
    respuesta = HttpResponse(
        content_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{nombre}"'},
    )
    respuesta.write("﻿")  # BOM: Excel abre los acentos correctamente
    escritor = csv.writer(respuesta)
    escritor.writerow(ENCABEZADOS_CSV)
    for m in movimientos.order_by("fecha", "id"):
        escritor.writerow(
            [
                m.fecha.isoformat(),
                m.get_tipo_display(),
                m.descripcion,
                m.categoria.nombre if m.categoria else "",
                m.concepto or "",
                m.monto,
                m.get_metodo_pago_display(),
                m.cuenta or "",
                m.cuenta_destino or "",
                m.persona or "",
                m.domicilio or "",
                "sí" if m.es_hormiga else "no",
                "sí" if m.es_extraordinario else "no",
                m.get_tipo_ingreso_display(),
            ]  # fmt: skip
        )
    return respuesta
