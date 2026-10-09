from collections.abc import Callable
from dataclasses import dataclass

from django.contrib import messages
from django.db import transaction
from django.db.models import ProtectedError, RestrictedError
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.catalogos.formularios import (
    FormularioCategoria,
    FormularioConcepto,
    FormularioCuenta,
    FormularioDomicilio,
    FormularioPersona,
)
from apps.catalogos.models import Categoria, Concepto, Cuenta, Domicilio, Persona
from apps.catalogos.servicios import tasa_sugerida
from apps.core.acceso import requiere_hogar
from apps.core.htmx import datos_actualizados, es_htmx, responder_formulario
from apps.core.templatetags.formato import dinero, porcentaje


@dataclass(frozen=True)
class Catalogo:
    titulo: str
    singular: str
    modelo: type
    formulario: type
    columnas: tuple[tuple[str, Callable], ...]


def _sugeridos(concepto):
    valores = [concepto.persona, concepto.cuenta, concepto.domicilio]
    return " · ".join(str(valor) for valor in valores if valor) or "—"


def _tasa(cuenta):
    tasa = tasa_sugerida(cuenta)
    if tasa is None:
        return "—"
    return (
        porcentaje(tasa)
        if cuenta.tasa_anual is not None
        else f"{porcentaje(tasa)} (promedio del mercado)"
    )


CATALOGOS = {
    "personas": Catalogo(
        "Personas", "persona", Persona, FormularioPersona, (("Parentesco", lambda o: o.parentesco),)
    ),
    "domicilios": Catalogo(
        "Domicilios",
        "domicilio",
        Domicilio,
        FormularioDomicilio,
        (("Dirección", lambda o: o.direccion),),
    ),
    "categorias": Catalogo(
        "Categorías", "categoría", Categoria, FormularioCategoria, (("Orden", lambda o: o.orden),)
    ),
    "conceptos": Catalogo(
        "Conceptos",
        "concepto",
        Concepto,
        FormularioConcepto,
        (("Categoría", lambda o: o.categoria), ("Sugeridos", _sugeridos)),
    ),
    "cuentas": Catalogo(
        "Cuentas",
        "cuenta",
        Cuenta,
        FormularioCuenta,
        (
            ("Tipo", lambda o: o.get_tipo_display()),
            ("Saldo", lambda o: dinero(o.saldo_actual)),
            ("Tasa", _tasa),
        ),
    ),
}


def _catalogo(nombre):
    catalogo = CATALOGOS.get(nombre)
    if catalogo is None:
        raise Http404("Catálogo desconocido")
    return catalogo


@requiere_hogar
def indice(request):
    return render(request, "catalogos/indice.html", {"catalogos": CATALOGOS})


@requiere_hogar
def lista(request, catalogo):
    datos = _catalogo(catalogo)
    objetos = datos.modelo.objects.del_hogar(request.hogar)
    if datos.modelo is Concepto:
        objetos = objetos.select_related("categoria", "persona", "cuenta", "domicilio")
    filas = [
        (objeto, [(encabezado, funcion(objeto)) for encabezado, funcion in datos.columnas])
        for objeto in objetos
    ]
    contexto = {"catalogo": datos, "nombre": catalogo, "filas": filas}
    return render(request, "catalogos/lista.html", contexto)


@requiere_hogar
def nuevo(request, catalogo):
    return _editar(request, catalogo, None)


@requiere_hogar
def editar(request, catalogo, pk):
    datos = _catalogo(catalogo)
    objeto = get_object_or_404(datos.modelo.objects.del_hogar(request.hogar), pk=pk)
    return _editar(request, catalogo, objeto)


@requiere_hogar
@require_POST
def eliminar(request, catalogo, pk):
    """RF-CAT-05: lo que tiene registros asociados no se borra, se desactiva."""
    datos = _catalogo(catalogo)
    objeto = get_object_or_404(datos.modelo.objects.del_hogar(request.hogar), pk=pk)
    try:
        with transaction.atomic():
            objeto.delete()
        messages.success(request, f"Se eliminó {objeto}.")
    except (RestrictedError, ProtectedError):
        objeto.activo = False
        objeto.save(update_fields=["activo", "actualizado_en"])
        messages.info(
            request, f"{objeto} tiene registros asociados: se desactivó en lugar de borrarse."
        )
    return datos_actualizados() if es_htmx(request) else redirect("catalogos:lista", catalogo)


def _editar(request, catalogo, objeto):
    datos = _catalogo(catalogo)
    post = request.POST if request.method == "POST" else None
    formulario = datos.formulario(post, instance=objeto, hogar=request.hogar)
    if post is not None and formulario.is_valid():
        formulario.save()
        return datos_actualizados() if es_htmx(request) else redirect("catalogos:lista", catalogo)
    titulo = f"{'Editar' if objeto else 'Agregar'} {datos.singular}"
    return responder_formulario(
        request, {"formulario": formulario, "titulo": titulo, "accion": request.path}
    )
