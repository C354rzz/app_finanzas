"""Reglas RN-01 a RN-04 del DEF: resumen del presupuesto mensual."""

from collections.abc import Iterable
from dataclasses import dataclass
from decimal import Decimal

from apps.calculos.comun import CERO

MENSUAL = "mensual"
ANUAL = "anual"
DIAS_POR_MES = Decimal("30")


@dataclass(frozen=True)
class LineaIngreso:
    monto: Decimal
    es_fijo: bool = True


@dataclass(frozen=True)
class LineaGasto:
    monto: Decimal
    periodicidad: str = MENSUAL
    es_fijo: bool = False
    con_tarjeta: bool = False
    es_hormiga: bool = False

    def monto_mensual(self) -> Decimal:
        """RN-03: un gasto anual cuenta como monto / 12 en todos los totales."""
        if self.periodicidad == MENSUAL:
            return self.monto
        if self.periodicidad == ANUAL:
            return self.monto / 12
        raise ValueError(f"Periodicidad desconocida: {self.periodicidad!r}")


@dataclass(frozen=True)
class ResumenPresupuesto:
    ingresos_fijos: Decimal
    ingresos_variables: Decimal
    ingresos_totales: Decimal
    gastos_fijos: Decimal
    gastos_variables: Decimal
    gastos_totales: Decimal
    disponible: Decimal
    meta_ahorro: Decimal
    presupuesto_hormiga: Decimal
    maximo_diario_hormiga: Decimal
    recorte_necesario: Decimal | None
    gasto_con_tarjeta: Decimal


def resumir_presupuesto(
    ingresos: Iterable[LineaIngreso],
    gastos: Iterable[LineaGasto],
    porcentaje_ahorro: Decimal,
) -> ResumenPresupuesto:
    """Calcula RN-01 (totales), RN-02 (meta de ahorro) y RN-04 (gastos hormiga)."""
    if not CERO <= porcentaje_ahorro <= 1:
        raise ValueError("El porcentaje de ahorro debe estar entre 0 y 1")
    ingresos = list(ingresos)
    gastos = list(gastos)
    if any(linea.monto < 0 for linea in [*ingresos, *gastos]):
        raise ValueError("Los montos no pueden ser negativos")

    ingresos_fijos = sum((i.monto for i in ingresos if i.es_fijo), CERO)
    ingresos_totales = sum((i.monto for i in ingresos), CERO)
    gastos_totales = sum((x.monto_mensual() for x in gastos), CERO)
    gastos_fijos = sum((x.monto_mensual() for x in gastos if x.es_fijo), CERO)
    hormiga = sum((x.monto_mensual() for x in gastos if x.es_hormiga), CERO)
    con_tarjeta = sum((x.monto_mensual() for x in gastos if x.con_tarjeta), CERO)

    disponible = ingresos_totales - gastos_totales
    meta_ahorro = ingresos_totales * porcentaje_ahorro
    faltante = disponible - meta_ahorro

    return ResumenPresupuesto(
        ingresos_fijos=ingresos_fijos,
        ingresos_variables=ingresos_totales - ingresos_fijos,
        ingresos_totales=ingresos_totales,
        gastos_fijos=gastos_fijos,
        gastos_variables=gastos_totales - gastos_fijos,
        gastos_totales=gastos_totales,
        disponible=disponible,
        meta_ahorro=meta_ahorro,
        presupuesto_hormiga=hormiga,
        maximo_diario_hormiga=hormiga / DIAS_POR_MES,
        recorte_necesario=None if faltante >= 0 else -faltante,
        gasto_con_tarjeta=con_tarjeta,
    )
