"""Reglas de clasificación del hogar (RN-12) y posibles duplicados (RN-11)."""

import re
import unicodedata
from datetime import timedelta
from decimal import Decimal

from django.db.models import F, Q

from apps.importacion.models import ReglaClasificacion
from apps.movimientos.models import Movimiento

DIAS_DUPLICADO = 2


def normalizar(texto):
    """Sin acentos, en minúsculas y con espacios simples."""
    sin_acentos = unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode()
    return " ".join(sin_acentos.lower().split())


def palabras(texto):
    """Solo las palabras (letras) del texto normalizado: «OXXO SUC 1234» → «oxxo suc»."""
    return " ".join(re.findall(r"[a-z]+", normalizar(texto)))


def patron_sugerido(descripcion):
    """Patrón para «recordar clasificación»: las dos primeras palabras de 3 o más letras."""
    utiles = [palabra for palabra in palabras(descripcion).split() if len(palabra) >= 3]
    return " ".join(utiles[:2])


def buscar_regla(hogar, emisor, descripcion):
    """RN-12: la primera regla (por prioridad) cuyas palabras aparecen completas."""
    texto = f" {palabras(descripcion)} "
    emisor_normal = normalizar(emisor)
    for regla in ReglaClasificacion.objects.del_hogar(hogar).order_by("prioridad", "-id"):
        if regla.emisor and normalizar(regla.emisor) not in emisor_normal:
            continue
        patron = palabras(regla.patron)
        if patron and f" {patron} " in texto:
            return regla
    return None


def aplicar_regla(propuesta, regla):
    """Copia a la propuesta los valores que la regla define; la regla manda sobre la IA."""
    if regla.concepto_id:
        propuesta.concepto = regla.concepto
        propuesta.categoria = regla.concepto.categoria
    elif regla.categoria_id:
        propuesta.categoria = regla.categoria
        if propuesta.concepto and propuesta.concepto.categoria_id != regla.categoria_id:
            propuesta.concepto = None
    if regla.persona_id:
        propuesta.persona = regla.persona
    if regla.domicilio_id:
        propuesta.domicilio = regla.domicilio
    if regla.es_hormiga is not None:
        propuesta.es_hormiga = regla.es_hormiga
    propuesta.regla = regla
    propuesta.confianza = Decimal("1")
    ReglaClasificacion.objects.filter(pk=regla.pk).update(veces_aplicada=F("veces_aplicada") + 1)


def buscar_duplicado(hogar, fecha, monto, cuenta=None):
    """RN-11: mismo monto, fecha a ±2 días y la misma cuenta (origen o destino) o sin cuenta."""
    consulta = Movimiento.objects.del_hogar(hogar).filter(
        monto=monto,
        fecha__range=(
            fecha - timedelta(days=DIAS_DUPLICADO),
            fecha + timedelta(days=DIAS_DUPLICADO),
        ),
    )
    if cuenta is not None:
        consulta = consulta.filter(
            Q(cuenta=cuenta) | Q(cuenta_destino=cuenta) | Q(cuenta__isnull=True)
        )
    return consulta.order_by("fecha", "id").first()
