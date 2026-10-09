"""Utilidades compartidas por los cálculos financieros (sin dependencias de Django)."""

from decimal import ROUND_HALF_UP, Decimal

CERO = Decimal("0")


def redondear(valor: Decimal, decimales: int = 2) -> Decimal:
    """Redondea al estilo comercial (0.005 → 0.01). Usar solo para mostrar o comparar."""
    return valor.quantize(Decimal(1).scaleb(-decimales), rounding=ROUND_HALF_UP)
