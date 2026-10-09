"""Regla RN-05 del DEF: ahorro mensual necesario para una meta con interés compuesto."""

from decimal import Decimal

from apps.calculos.comun import CERO


def aporte_mensual_meta(
    monto_objetivo: Decimal, ahorro_actual: Decimal, meses: int, tasa_anual: Decimal
) -> Decimal:
    """Aporte = max(0, (M − A·(1+i)^n)·i / ((1+i)^n − 1)), con i = tasa/12."""
    if meses <= 0:
        raise ValueError("Los meses deben ser mayores a cero")
    if tasa_anual < 0:
        raise ValueError("La tasa no puede ser negativa")
    i = tasa_anual / 12
    if i == 0:
        aporte = (monto_objetivo - ahorro_actual) / meses
    else:
        factor = (1 + i) ** meses
        aporte = (monto_objetivo - ahorro_actual * factor) * i / (factor - 1)
    return max(CERO, aporte)
