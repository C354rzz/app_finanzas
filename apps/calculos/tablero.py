"""RF-TAB-02 y RF-TAB-03: avance por categoría, semáforo y distribución del gasto."""

from decimal import Decimal

from apps.calculos.comun import CERO

VERDE, AMBAR, ROJO = "verde", "ambar", "rojo"
LIMITE_VERDE = Decimal("0.80")


def avance(gastado, presupuesto):
    """Fracción gastada del presupuesto; None si no hay presupuesto."""
    if presupuesto <= 0:
        return None
    return gastado / presupuesto


def semaforo(gastado, presupuesto):
    """Verde < 80 %; ámbar 80–100 %; rojo > 100 % o gasto sin presupuesto."""
    fraccion = avance(gastado, presupuesto)
    if fraccion is None:
        return ROJO if gastado > 0 else VERDE
    if fraccion < LIMITE_VERDE:
        return VERDE
    if fraccion <= 1:
        return AMBAR
    return ROJO


def distribucion(montos):
    """Participación de cada monto en el total (0 si el total es 0)."""
    total = sum(montos.values(), CERO)
    if total <= 0:
        return {clave: CERO for clave in montos}
    return {clave: monto / total for clave, monto in montos.items()}
