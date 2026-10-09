"""Filtros de presentación (RNF-08): moneda MXN, porcentajes y barras."""

from decimal import Decimal

from django import template

from apps.calculos.comun import redondear

register = template.Library()


@register.filter
def dinero(valor):
    """$1,234.56; negativos como -$1,234.56; vacío como —."""
    if valor is None or valor == "":
        return "—"
    valor = redondear(Decimal(valor))
    signo = "-" if valor < 0 else ""
    return f"{signo}${abs(valor):,.2f}"


@register.filter
def porcentaje(valor, decimales=2):
    """Fracción → porcentaje: 0.9632 → 96.32%."""
    if valor is None or valor == "":
        return "—"
    decimales = int(decimales)
    return f"{redondear(Decimal(valor) * 100, decimales):,.{decimales}f}%"


@register.filter
def ancho_barra(valor):
    """Ancho de una barra de progreso (0–100) a partir de una fracción."""
    if valor is None or valor == "":
        return 0
    return int(min(max(Decimal(valor), Decimal(0)), Decimal(1)) * 100)
