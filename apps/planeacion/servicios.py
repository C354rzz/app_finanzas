"""Servicios de planeación: metas, deudas, patrimonio y simulaciones."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from apps.calculos.comun import CERO
from apps.core.fechas import sumar_meses
from apps.planeacion.mensajes import mensaje_metas
from apps.planeacion.models import MetaAhorro


@dataclass(frozen=True)
class FilaMeta:
    meta: MetaAhorro
    aporte: Decimal
    fecha_fin: date


@dataclass(frozen=True)
class ResumenMetas:
    filas: list
    total_mensual: Decimal
    porcentaje_ingresos: Decimal | None
    nivel: str
    mensaje: str


def resumir_metas(hogar, resumen):
    """RF-MET-02 y RF-MET-03 con el disponible e ingresos de un resumen de presupuesto."""
    metas = MetaAhorro.objects.del_hogar(hogar).filter(activa=True).select_related("cuenta")
    filas = [
        FilaMeta(
            meta=meta,
            aporte=meta.aporte_mensual(),
            fecha_fin=sumar_meses(meta.fecha_inicio, meta.meses),
        )
        for meta in metas
    ]
    total = sum((fila.aporte for fila in filas), CERO)
    ingresos = resumen.ingresos_totales
    nivel, mensaje = mensaje_metas(resumen.disponible, total)
    return ResumenMetas(
        filas=filas,
        total_mensual=total,
        porcentaje_ingresos=total / ingresos if ingresos > 0 else None,
        nivel=nivel,
        mensaje=mensaje,
    )
