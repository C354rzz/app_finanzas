"""Pantallas de importación (P10) y revisión de documentos (P11)."""

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db.models import Count, Q
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.calculos.comun import redondear
from apps.core.acceso import requiere_hogar
from apps.core.htmx import datos_actualizados, es_htmx, responder_formulario
from apps.importacion import servicios
from apps.importacion.formularios import FormularioPropuesta, FormularioSubida
from apps.importacion.models import Documento, MovimientoPropuesto

PENDIENTE = MovimientoPropuesto.Estado.PENDIENTE


def _lista(hogar):
    servicios.marcar_atascados(hogar)
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
    documento = _documento(request, pk)
    if documento.estado in Documento.ESTADOS_EN_CURSO:
        messages.error(request, "Espera a que termine de procesarse para eliminarlo.")
        return redirect("importacion:importar")
    servicios.eliminar_documento(documento)
    messages.success(request, "Se eliminó el documento; los movimientos aceptados se conservan.")
    return redirect("importacion:importar")


def _propuesta(request, pk):
    consulta = MovimientoPropuesto.objects.del_hogar(request.hogar).select_related("documento")
    return get_object_or_404(consulta, pk=pk)


def _volver(request, documento):
    if es_htmx(request):
        return datos_actualizados()
    return redirect("importacion:revisar", documento.pk)


@requiere_hogar
def propuesta_editar(request, pk):
    propuesta = _propuesta(request, pk)
    if propuesta.estado != PENDIENTE:
        raise Http404("La propuesta ya se revisó.")
    datos = request.POST if request.method == "POST" else None
    formulario = FormularioPropuesta(datos, instance=propuesta, hogar=request.hogar)
    if datos is not None and formulario.is_valid():
        formulario.save()
        return _volver(request, propuesta.documento)
    contexto = {"formulario": formulario, "titulo": "Editar propuesta", "accion": request.path}
    return responder_formulario(request, contexto)


@requiere_hogar
@require_POST
def propuesta_aceptar(request, pk):
    propuesta = _propuesta(request, pk)
    try:
        servicios.aceptar_propuesta(
            propuesta, request.user, recordar=request.POST.get("recordar") == "on"
        )
    except ValidationError:
        messages.error(request, "No se pudo aceptar la propuesta; revisa el mensaje en rojo.")
    return _volver(request, propuesta.documento)


@requiere_hogar
@require_POST
def propuesta_descartar(request, pk):
    propuesta = _propuesta(request, pk)
    servicios.descartar_propuesta(propuesta)
    return _volver(request, propuesta.documento)


@requiere_hogar
@require_POST
def aceptar_todo(request, pk):
    documento = _documento(request, pk)
    aceptadas, con_error = servicios.aceptar_no_duplicados(documento, request.user)
    messages.success(request, f"Se aceptaron {aceptadas} propuesta(s).")
    if con_error:
        messages.error(request, f"{con_error} propuesta(s) necesitan corrección.")
    return _volver(request, documento)


@requiere_hogar
@require_POST
def descartar_todo(request, pk):
    documento = _documento(request, pk)
    servicios.descartar_todas(documento)
    return _volver(request, documento)


@requiere_hogar
@require_POST
def actualizar_saldo(request, pk):
    documento = _documento(request, pk)
    if servicios.actualizar_saldo(documento):
        messages.success(request, f"Se actualizó el saldo de {documento.cuenta}.")
    else:
        messages.error(
            request,
            "No se actualizó el saldo: primero acepta o descarta los pagos a esta cuenta, "
            "o el estado de cuenta es anterior al último saldo registrado.",
        )
    return redirect("importacion:revisar", documento.pk)
