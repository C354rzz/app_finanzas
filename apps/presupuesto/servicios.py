from django.db import transaction

from apps.calculos.comun import redondear
from apps.calculos.presupuesto import LineaGasto, LineaIngreso, resumir_presupuesto
from apps.core.fechas import validar_mes
from apps.presupuesto.models import (
    PlantillaPresupuesto,
    PresupuestoMes,
    PresupuestoMesGasto,
    PresupuestoMesIngreso,
)


def obtener_plantilla(hogar):
    plantilla, _ = PlantillaPresupuesto.objects.get_or_create(hogar=hogar)
    return plantilla


@transaction.atomic
def obtener_presupuesto_mes(hogar, anio, mes):
    """RF-PRE-03: la primera consulta de un mes lo crea copiando la plantilla."""
    validar_mes(anio, mes)
    plantilla = obtener_plantilla(hogar)
    presupuesto, creado = PresupuestoMes.objects.get_or_create(
        hogar=hogar,
        anio=anio,
        mes=mes,
        defaults={"porcentaje_ahorro": plantilla.porcentaje_ahorro},
    )
    if creado:
        _copiar_plantilla(plantilla, presupuesto)
    return presupuesto


@transaction.atomic
def resincronizar_mes(presupuesto):
    """RF-PRE-04: reemplaza el presupuesto del mes por la plantilla actual."""
    plantilla = obtener_plantilla(presupuesto.hogar)
    presupuesto.ingresos.all().delete()
    presupuesto.gastos.all().delete()
    presupuesto.porcentaje_ahorro = plantilla.porcentaje_ahorro
    presupuesto.save(update_fields=["porcentaje_ahorro", "actualizado_en"])
    _copiar_plantilla(plantilla, presupuesto)


def _copiar_plantilla(plantilla, presupuesto):
    hogar = presupuesto.hogar
    PresupuestoMesIngreso.objects.bulk_create(
        PresupuestoMesIngreso(
            hogar=hogar,
            presupuesto=presupuesto,
            nombre=i.nombre,
            tipo_ingreso=i.tipo_ingreso,
            es_fijo=i.es_fijo,
            monto=i.monto,
            persona_id=i.persona_id,
        )
        for i in plantilla.ingresos.all()
    )
    PresupuestoMesGasto.objects.bulk_create(
        PresupuestoMesGasto(
            hogar=hogar,
            presupuesto=presupuesto,
            concepto_id=g.concepto_id,
            monto_mensual=redondear(g.monto_mensual()),
            es_fijo=g.es_fijo,
            con_tarjeta=g.con_tarjeta,
            es_hormiga=g.es_hormiga,
        )
        for g in plantilla.gastos.all()
    )


def resumen_plantilla(plantilla):
    """RN-01 a RN-04 sobre la plantilla (con el prorrateo anual exacto)."""
    return resumir_presupuesto(
        [LineaIngreso(monto=i.monto, es_fijo=i.es_fijo) for i in plantilla.ingresos.all()],
        [
            LineaGasto(
                monto=g.monto,
                periodicidad=g.periodicidad,
                es_fijo=g.es_fijo,
                con_tarjeta=g.con_tarjeta,
                es_hormiga=g.es_hormiga,
            )
            for g in plantilla.gastos.all()
        ],
        plantilla.porcentaje_ahorro,
    )


def ingresos_del_mes(presupuesto, persona=None, domicilio=None):
    """Un domicilio no tiene ingresos; por persona, solo los suyos."""
    if domicilio is not None:
        return presupuesto.ingresos.none()
    ingresos = presupuesto.ingresos.all()
    return ingresos.filter(persona=persona) if persona is not None else ingresos


def gastos_del_mes(presupuesto, persona=None, domicilio=None):
    """Gastos presupuestados; persona y domicilio se toman del concepto."""
    gastos = presupuesto.gastos.select_related("concepto__categoria")
    if persona is not None:
        gastos = gastos.filter(concepto__persona=persona)
    if domicilio is not None:
        gastos = gastos.filter(concepto__domicilio=domicilio)
    return gastos


def resumen_mes(presupuesto, persona=None, domicilio=None):
    return resumir_presupuesto(
        [
            LineaIngreso(monto=i.monto, es_fijo=i.es_fijo)
            for i in ingresos_del_mes(presupuesto, persona, domicilio)
        ],
        [
            LineaGasto(
                monto=g.monto_mensual,
                es_fijo=g.es_fijo,
                con_tarjeta=g.con_tarjeta,
                es_hormiga=g.es_hormiga,
            )
            for g in gastos_del_mes(presupuesto, persona, domicilio)
        ],
        presupuesto.porcentaje_ahorro,
    )
