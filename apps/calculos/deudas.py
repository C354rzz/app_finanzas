"""Reglas RN-06, RN-08 y RN-10 del DEF: avance de créditos, uso de tarjetas y patrimonio."""

from collections.abc import Iterable
from dataclasses import dataclass
from decimal import Decimal

from apps.calculos.comun import CERO

NIVEL_BUENO = "bueno"
NIVEL_CUIDADO = "cuidado"
NIVEL_RIESGO = "riesgo"
LIMITE_BUENO = Decimal("0.30")
LIMITE_CUIDADO = Decimal("0.50")


@dataclass(frozen=True)
class TarjetaCredito:
    saldo: Decimal
    linea: Decimal


def _deuda(saldo: Decimal) -> Decimal:
    """Un saldo a favor (negativo) no es deuda."""
    return max(CERO, saldo)


def porcentaje_completado(deuda_inicial: Decimal, deuda_actual: Decimal) -> Decimal | None:
    """RN-06: 1 − actual / inicial; None si no hay deuda inicial."""
    if deuda_inicial <= 0:
        return None
    return 1 - deuda_actual / deuda_inicial


def uso_de_credito(tarjetas: Iterable[TarjetaCredito]) -> Decimal | None:
    """RN-08: Σ saldo / Σ línea de crédito; None si no hay línea."""
    tarjetas = list(tarjetas)
    linea_total = sum((t.linea for t in tarjetas), CERO)
    if linea_total <= 0:
        return None
    return sum((_deuda(t.saldo) for t in tarjetas), CERO) / linea_total


def nivel_de_uso(uso: Decimal) -> str:
    """< 30% bueno; 30–50% cuidado; > 50% riesgo."""
    if uso < LIMITE_BUENO:
        return NIVEL_BUENO
    if uso <= LIMITE_CUIDADO:
        return NIVEL_CUIDADO
    return NIVEL_RIESGO


def patrimonio_neto(
    activos: Iterable[Decimal],
    saldos_prestamos: Iterable[Decimal],
    saldos_tarjetas: Iterable[Decimal],
) -> Decimal:
    """RN-10: Σ activos − Σ préstamos − Σ tarjetas."""
    deudas = sum((_deuda(s) for s in [*saldos_prestamos, *saldos_tarjetas]), CERO)
    return sum(activos, CERO) - deudas
