"""Composición del tablero del mes (P2). No tiene modelos propios."""

from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal

from django.db.models import Q

from apps.calculos.comun import CERO
from apps.calculos.deudas import NIVEL_CUIDADO, NIVEL_RIESGO
from apps.calculos.presupuesto import ResumenPresupuesto
from apps.calculos.tablero import avance, distribucion, semaforo
from apps.catalogos.models import Categoria
from apps.catalogos.servicios import ResumenDeudas, resumir_deudas
from apps.core.templatetags.formato import dinero, porcentaje
from apps.movimientos.consultas import Filtros, Totales, movimientos_del_mes, totales
from apps.planeacion.servicios import (
    Patrimonio,
    ResumenMetas,
    calcular_patrimonio,
    resumir_metas,
)
from apps.presupuesto.mensajes import mensaje_disponible
from apps.presupuesto.servicios import gastos_del_mes, obtener_presupuesto_mes, resumen_mes


@dataclass(frozen=True)
class FilaCategoria:
    categoria: Categoria
    presupuesto: Decimal
    gastado: Decimal
    restante: Decimal
    avance: Decimal | None
    color: str
    participacion: Decimal


@dataclass(frozen=True)
class Alerta:
    nivel: str
    mensaje: str


@dataclass(frozen=True)
class Tablero:
    anio: int
    mes: int
    filtrado: bool
    resumen: ResumenPresupuesto
    reales: Totales
    categorias: list
    gasto_anual_estimado: Decimal
    deudas: ResumenDeudas
    mensaje_disponible: tuple | None
    alertas: list
    metas: ResumenMetas | None
    patrimonio: Patrimonio


def armar_tablero(hogar, anio, mes, persona=None, domicilio=None):
    """RF-TAB-01..06. Con persona o domicilio, solo se filtran gastos (e ingresos por persona)."""
    presupuesto = obtener_presupuesto_mes(hogar, anio, mes)
    resumen = resumen_mes(presupuesto, persona=persona, domicilio=domicilio)
    filtros = Filtros(persona=persona, domicilio=domicilio)
    reales = totales(movimientos_del_mes(hogar, anio, mes, filtros))
    filtrado = persona is not None or domicilio is not None
    deudas = resumir_deudas(hogar)
    metas = None if filtrado else resumir_metas(hogar, resumen)
    return Tablero(
        anio=anio,
        mes=mes,
        filtrado=filtrado,
        resumen=resumen,
        reales=reales,
        categorias=_filas_por_categoria(
            hogar, gastos_del_mes(presupuesto, persona, domicilio), reales
        ),
        gasto_anual_estimado=resumen.gastos_totales * 12,
        deudas=deudas,
        mensaje_disponible=(
            None if filtrado else mensaje_disponible(resumen.disponible, resumen.meta_ahorro)
        ),
        alertas=_alertas(resumen, reales, deudas, filtrado, metas),
        metas=metas,
        patrimonio=calcular_patrimonio(hogar),
    )


def _filas_por_categoria(hogar, gastos_presupuestados, reales):
    presupuestado = defaultdict(lambda: CERO)
    for renglon in gastos_presupuestados:
        presupuestado[renglon.concepto.categoria_id] += renglon.monto_mensual
    gastado = {categoria.pk: total for categoria, total in reales.por_categoria}
    con_datos = set(presupuestado) | set(gastado)
    categorias = list(
        Categoria.objects.del_hogar(hogar).filter(Q(activo=True) | Q(pk__in=con_datos))
    )
    participacion = distribucion({c.pk: presupuestado[c.pk] for c in categorias})
    filas = []
    for categoria in categorias:
        monto_presupuesto = presupuestado[categoria.pk]
        monto_gastado = gastado.get(categoria.pk, CERO)
        filas.append(
            FilaCategoria(
                categoria=categoria,
                presupuesto=monto_presupuesto,
                gastado=monto_gastado,
                restante=monto_presupuesto - monto_gastado,
                avance=avance(monto_gastado, monto_presupuesto),
                color=semaforo(monto_gastado, monto_presupuesto),
                participacion=participacion[categoria.pk],
            )
        )
    return filas


def _alertas(resumen, reales, deudas, filtrado, metas=None):
    """RF-TAB-06: RN-08, RN-09, disponible negativo y meta de ahorro no alcanzable."""
    alertas = []
    if deudas.nivel in (NIVEL_CUIDADO, NIVEL_RIESGO):
        alertas.append(
            Alerta(
                deudas.nivel,
                f"Uso de tus tarjetas de crédito: {porcentaje(deudas.uso)} ({deudas.nivel}). "
                "Lo sano es menos de 30%.",
            )
        )
    for nombre in deudas.tarjetas_con_intereses:
        alertas.append(
            Alerta(NIVEL_CUIDADO, f"Estás pagando intereses en {nombre}: no pagas el total.")
        )
    if filtrado:
        return alertas
    if reales.disponible < 0:
        alertas.append(
            Alerta(
                NIVEL_RIESGO,
                f"Este mes llevas {dinero(-reales.disponible)} más de gastos que de ingresos.",
            )
        )
    if resumen.recorte_necesario is not None:
        alertas.append(
            Alerta(
                NIVEL_CUIDADO,
                "Con este presupuesto no alcanzas tu meta de ahorro: "
                f"te faltan {dinero(resumen.recorte_necesario)} al mes.",
            )
        )
    if metas is not None and metas.filas and metas.total_mensual > resumen.disponible:
        alertas.append(
            Alerta(
                NIVEL_CUIDADO,
                f"Tus metas de ahorro piden {dinero(metas.total_mensual)} al mes y el disponible "
                f"de tu presupuesto es {dinero(resumen.disponible)}.",
            )
        )
    return alertas
