"""Pantallas de importación (P10) y revisión de documentos (P11)."""

from django.contrib import messages
from django.db.models import Count, Q
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.calculos.comun import redondear
from apps.core.acceso import requiere_hogar
from apps.importacion import servicios
from apps.importacion.formularios import FormularioSubida
from apps.importacion.models import Documento, MovimientoPropuesto

PENDIENTE = MovimientoPropuesto.Estado.PENDIENTE


def _lista(hogar):
    documentos = list(
        Documento.objects.del_hogar(hogar)
        .annotate(pendientes=Count("propuestas", filter=Q(propuestas__estado=PENDIENTE)))
        .order_by("-creado_en")[:50]
    )
    en_curso = any(d.estado in Documento.ESTADOS_EN_CURSO for d in documentos)
    return {"documentos": documentos, "hay_pendientes": en_curso}


def _documento(request, pk):
    return get_object_or_404(Documento.objects.del_hogar(request.hogar), pk=pk)


def _propuestas(documento):
    propuestas = documento.propuestas.select_related(
        "categoria", "concepto__categoria", "persona", "domicilio", "cuenta", "cuenta_destino",
        "posible_duplicado_de", "regla",
    )  # fmt: skip
    pendientes = [p for p in propuestas if p.estado == PENDIENTE]
    revisadas = [p for p in propuestas if p.estado != PENDIENTE]
    return pendientes, revisadas


@requiere_hogar
def importar(request):
    if request.method == "POST":
        formulario = FormularioSubida(request.POST, request.FILES, hogar=request.hogar)
        if formulario.is_valid():
            documentos, rechazos = servicios.registrar_archivos(
                request.hogar,
                request.user,
                formulario.cleaned_data["archivos"],
                cuenta=formulario.cleaned_data["cuenta"],
            )
            if documentos:
                messages.success(
                    request, f"Se subieron {len(documentos)} documento(s); se están procesando."
                )
            for rechazo in rechazos:
                messages.error(request, f"{rechazo.nombre}: {rechazo.motivo}.")
            return redirect("importacion:importar")
    else:
        formulario = FormularioSubida(hogar=request.hogar)
    contexto = {
        "formulario": formulario,
        "costo_mes": f"{redondear(servicios.costo_del_mes(request.hogar))}",
        **_lista(request.hogar),
    }
    return render(request, "importacion/importar.html", contexto)


@requiere_hogar
def documentos(request):
    return render(request, "importacion/_documentos.html", _lista(request.hogar))


@requiere_hogar
def revisar(request, pk):
    documento = _documento(request, pk)
    pendientes, revisadas = _propuestas(documento)
    contexto = {"documento": documento, "pendientes": pendientes, "revisadas": revisadas}
    return render(request, "importacion/revisar.html", contexto)


@requiere_hogar
def original(request, pk):
    """IMP-14: el PDF solo se sirve a su hogar (no hay URL pública de media)."""
    documento = _documento(request, pk)
    try:
        archivo = documento.archivo.open("rb")
    except (FileNotFoundError, ValueError) as error:
        raise Http404 from error
    return FileResponse(archivo, content_type="application/pdf", filename=documento.nombre_original)


@requiere_hogar
@require_POST
def reintentar(request, pk):
    documento = _documento(request, pk)
    if documento.estado == Documento.Estado.ERROR:
        servicios.reintentar(documento)
        messages.success(request, "El documento se volverá a procesar.")
    return redirect("importacion:importar")


@requiere_hogar
@require_POST
def eliminar(request, pk):
    servicios.eliminar_documento(_documento(request, pk))
    messages.success(request, "Se eliminó el documento; los movimientos aceptados se conservan.")
    return redirect("importacion:importar")
