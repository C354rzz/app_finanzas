"""Servicios de planeación: metas, deudas, patrimonio y simulaciones."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from apps.calculos.comun import CERO
from apps.calculos.deudas import (
    TarjetaCredito,
    nivel_de_uso,
    patrimonio_neto,
    porcentaje_completado,
    uso_de_credito,
)
from apps.catalogos.models import Cuenta
from apps.catalogos.servicios import ResumenDeudas, resumir_deudas, tasa_sugerida
from apps.core.fechas import sumar_meses
from apps.movimientos.consultas import Filtros, movimientos_del_mes, totales
from apps.movimientos.models import MetodoPago, Movimiento
from apps.planeacion.mensajes import mensaje_metas, mensaje_tarjeta, mensaje_uso
from apps.planeacion.models import Activo, MetaAhorro
from apps.presupuesto.servicios import obtener_presupuesto_mes, resumen_mes


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


@dataclass(frozen=True)
class FilaTarjeta:
    cuenta: Cuenta
    tasa: Decimal | None
    tasa_de_mercado: bool
    uso: Decimal | None
    nivel: str | None
    mensaje: str


@dataclass(frozen=True)
class FilaCredito:
    cuenta: Cuenta
    completado: Decimal | None


@dataclass(frozen=True)
class VistaDeudas:
    tarjetas: list
    creditos: list
    resumen: ResumenDeudas
    mensaje_uso: str
    gasto_tarjeta_presupuesto: Decimal
    gasto_tarjeta_real: Decimal


def vista_deudas(hogar, anio, mes):
    """RF-DEU-01..04 con las cuentas activas y el presupuesto y gastos del mes."""
    cuentas = Cuenta.objects.del_hogar(hogar).filter(activo=True)
    tarjetas = []
    for tarjeta in cuentas.filter(tipo=Cuenta.Tipo.CREDITO):
        tasa = tasa_sugerida(tarjeta)
        uso = uso_de_credito(
            [TarjetaCredito(saldo=tarjeta.saldo_actual, linea=tarjeta.linea_credito or CERO)]
        )
        tarjetas.append(
            FilaTarjeta(
                cuenta=tarjeta,
                tasa=tasa,
                tasa_de_mercado=tarjeta.tasa_anual is None and tasa is not None,
                uso=uso,
                nivel=None if uso is None else nivel_de_uso(uso),
                mensaje=mensaje_tarjeta(tarjeta.paga_total_mensual),
            )
        )
    creditos = [
        FilaCredito(
            cuenta=credito,
            completado=porcentaje_completado(credito.monto_inicial or CERO, credito.saldo_actual),
        )
        for credito in cuentas.filter(tipo=Cuenta.Tipo.PRESTAMO)
    ]
    resumen = resumir_deudas(hogar)
    filtros = Filtros(tipo=Movimiento.Tipo.GASTO, metodo_pago=MetodoPago.TARJETA_CREDITO)
    return VistaDeudas(
        tarjetas=tarjetas,
        creditos=creditos,
        resumen=resumen,
        mensaje_uso=mensaje_uso(resumen.nivel),
        gasto_tarjeta_presupuesto=resumen_mes(
            obtener_presupuesto_mes(hogar, anio, mes)
        ).gasto_con_tarjeta,
        gasto_tarjeta_real=totales(movimientos_del_mes(hogar, anio, mes, filtros)).gastos,
    )


@dataclass(frozen=True)
class Patrimonio:
    activos: list
    total_activos: Decimal
    deuda_creditos: Decimal
    deuda_tarjetas: Decimal
    neto: Decimal


def calcular_patrimonio(hogar):
    """RN-10: Σ activos − Σ saldos de préstamos − Σ saldos de tarjetas."""
    activos = list(
        Activo.objects.del_hogar(hogar).filter(activo=True).select_related("domicilio", "cuenta")
    )
    deudas = resumir_deudas(hogar)
    total = sum((activo.valor_actual for activo in activos), CERO)
    return Patrimonio(
        activos=activos,
        total_activos=total,
        deuda_creditos=deudas.total_creditos,
        deuda_tarjetas=deudas.total_tarjetas,
        neto=patrimonio_neto([total], [deudas.total_creditos], [deudas.total_tarjetas]),
    )
