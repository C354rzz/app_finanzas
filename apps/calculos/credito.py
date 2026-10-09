"""Regla RN-07 del DEF: tabla de amortización con comisión y pagos anticipados."""

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal

from apps.calculos.comun import CERO

# Residuo por debajo del cual el saldo se considera liquidado (precisión de Decimal).
UMBRAL_LIQUIDADO = Decimal("0.005")


@dataclass(frozen=True)
class FilaAmortizacion:
    mes: int
    mensualidad: Decimal
    intereses: Decimal
    capital: Decimal
    saldo_final: Decimal
    capital_acumulado: Decimal
    pago_anticipado: Decimal


@dataclass(frozen=True)
class Amortizacion:
    capital_inicial: Decimal
    tasa_mensual: Decimal
    filas: tuple[FilaAmortizacion, ...]

    @property
    def mensualidad(self) -> Decimal:
        return self.filas[0].mensualidad if self.filas else CERO

    @property
    def total_intereses(self) -> Decimal:
        return sum((f.intereses for f in self.filas), CERO)


def tasa_efectiva_mensual(tasa_anual: Decimal) -> Decimal:
    """(1 + tasa anual)^(1/12) − 1, igual que el simulador del Excel."""
    return (1 + tasa_anual) ** (Decimal(1) / Decimal(12)) - 1


def _pago_nivelado(tasa: Decimal, periodos: int, saldo: Decimal) -> Decimal:
    """Equivalente a PMT(tasa, periodos, -saldo) de Excel."""
    if tasa == 0:
        return saldo / periodos
    return saldo * tasa / (1 - (1 + tasa) ** -periodos)


def amortizar(
    monto: Decimal,
    tasa_anual: Decimal,
    meses: int,
    comision_apertura: Decimal = CERO,
    pagos_anticipados: Mapping[int, Decimal] | None = None,
) -> Amortizacion:
    pagos_anticipados = dict(pagos_anticipados or {})
    if monto <= 0:
        raise ValueError("El monto debe ser mayor a cero")
    if meses <= 0:
        raise ValueError("Los meses deben ser mayores a cero")
    if tasa_anual < 0:
        raise ValueError("La tasa no puede ser negativa")
    if comision_apertura < 0:
        raise ValueError("La comisión no puede ser negativa")
    for mes, abono in pagos_anticipados.items():
        if not 1 <= mes <= meses:
            raise ValueError(f"El mes {mes} del pago anticipado está fuera del plazo")
        if abono < 0:
            raise ValueError("Un pago anticipado no puede ser negativo")

    tasa = tasa_efectiva_mensual(tasa_anual)
    capital_inicial = monto * (1 + comision_apertura)
    saldo = capital_inicial
    acumulado = CERO
    filas = []
    for mes in range(1, meses + 1):
        if saldo <= 0:
            break
        pago = _pago_nivelado(tasa, meses - mes + 1, saldo)
        intereses = saldo * tasa
        capital_regular = pago - intereses
        anticipado = min(pagos_anticipados.get(mes, CERO), saldo - capital_regular)
        capital = capital_regular + anticipado
        saldo -= capital
        if abs(saldo) < UMBRAL_LIQUIDADO:
            saldo = CERO
        acumulado += capital
        filas.append(
            FilaAmortizacion(
                mes=mes,
                mensualidad=pago + anticipado,
                intereses=intereses,
                capital=capital,
                saldo_final=saldo,
                capital_acumulado=acumulado,
                pago_anticipado=anticipado,
            )
        )
    return Amortizacion(capital_inicial=capital_inicial, tasa_mensual=tasa, filas=tuple(filas))
