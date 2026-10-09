"""Consultas de lectura de movimientos: filtros (RF-MOV-04) y totales (RF-MOV-06)."""

from dataclasses import dataclass
from decimal import Decimal

from django.db.models import Q, Sum

from apps.calculos.comun import CERO
from apps.catalogos.models import Categoria, Cuenta, Domicilio, Persona
from apps.core.fechas import rango_del_mes
from apps.movimientos.models import MetodoPago, Movimiento


@dataclass(frozen=True)
class Filtros:
    tipo: str = ""
    categoria: Categoria | None = None
    persona: Persona | None = None
    domicilio: Domicilio | None = None
    cuenta: Cuenta | None = None
    metodo_pago: str = ""
    texto: str = ""


@dataclass(frozen=True)
class Totales:
    ingresos: Decimal
    ingresos_extra: Decimal
    gastos: Decimal
    por_categoria: list
    por_metodo: list
    por_cuenta: list

    @property
    def disponible(self):
        """RN-15: ingresos reales (con extraordinarios) − gastos reales."""
        return self.ingresos - self.gastos


def movimientos_entre(hogar, inicio, fin, filtros=Filtros()):
    consulta = (
        Movimiento.objects.del_hogar(hogar)
        .filter(fecha__range=(inicio, fin))
        .select_related("categoria", "concepto", "cuenta", "cuenta_destino", "persona", "domicilio")
    )
    for campo in ("tipo", "categoria", "persona", "domicilio", "metodo_pago"):
        valor = getattr(filtros, campo)
        if valor:
            consulta = consulta.filter(**{campo: valor})
    if filtros.cuenta:
        consulta = consulta.filter(Q(cuenta=filtros.cuenta) | Q(cuenta_destino=filtros.cuenta))
    if filtros.texto:
        texto = filtros.texto
        consulta = consulta.filter(
            Q(descripcion__icontains=texto)
            | Q(notas__icontains=texto)
            | Q(concepto__nombre__icontains=texto)
        )
    return consulta


def movimientos_del_mes(hogar, anio, mes, filtros=Filtros()):
    inicio, fin = rango_del_mes(anio, mes)
    return movimientos_entre(hogar, inicio, fin, filtros)


def totales(movimientos):
    """Totales del mes; transferencias y pagos de deuda son neutrales (RN-14)."""
    gastos = movimientos.filter(tipo=Movimiento.Tipo.GASTO).order_by()
    ingresos = movimientos.filter(tipo=Movimiento.Tipo.INGRESO).order_by()
    por_categoria = _agrupar(gastos, "categoria")
    categorias = Categoria.objects.in_bulk([i for i in por_categoria if i is not None])
    por_cuenta = _agrupar(gastos, "cuenta")
    cuentas = Cuenta.objects.in_bulk([i for i in por_cuenta if i is not None])
    return Totales(
        ingresos=_suma(ingresos),
        ingresos_extra=_suma(ingresos.filter(es_extraordinario=True)),
        gastos=_suma(gastos),
        por_categoria=sorted(
            ((categorias[i], total) for i, total in por_categoria.items() if i is not None),
            key=lambda par: (par[0].orden, par[0].nombre),
        ),
        por_metodo=_ordenar(
            (MetodoPago(metodo).label, total)
            for metodo, total in _agrupar(gastos, "metodo_pago").items()
        ),
        por_cuenta=_ordenar(
            (cuentas[i].nombre if i else "Sin cuenta", total) for i, total in por_cuenta.items()
        ),
    )


def _suma(consulta):
    return consulta.aggregate(total=Sum("monto"))["total"] or CERO


def _agrupar(consulta, campo):
    filas = consulta.values(campo).annotate(total=Sum("monto"))
    return {fila[campo]: fila["total"] for fila in filas}


def _ordenar(pares):
    return sorted(pares, key=lambda par: (-par[1], par[0]))
