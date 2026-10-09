from dataclasses import dataclass
from decimal import Decimal

from apps.calculos.comun import CERO
from apps.calculos.deudas import TarjetaCredito, nivel_de_uso, uso_de_credito
from apps.catalogos.models import Categoria, Cuenta

# Las 12 categorías del Excel "Financial Planner template", en su orden original.
CATEGORIAS_INICIALES = [
    ("Casa", "🏡"),
    ("Comida", "🥑"),
    ("Familia", "❤️"),
    ("Transporte", "🚓"),
    ("Viajes", "✈️"),
    ("Deudas", "🏦"),
    ("Salud", "🚑"),
    ("Suscripciones", "📺"),
    ("Gastos anuales", "🗓️"),
    ("Cuidado personal", "💅"),
    ("Entretenimiento", "📽️"),
    ("Otros", "🛸"),
]


def sembrar_catalogos(hogar):
    """Crea las categorías iniciales que falten. Devuelve cuántas creó."""
    creadas = 0
    for orden, (nombre, icono) in enumerate(CATEGORIAS_INICIALES, start=1):
        _, nueva = Categoria.objects.get_or_create(
            hogar=hogar, nombre=nombre, defaults={"icono": icono, "orden": orden}
        )
        creadas += nueva
    return creadas


@dataclass(frozen=True)
class ResumenDeudas:
    total_tarjetas: Decimal
    total_creditos: Decimal
    mensualidades: Decimal
    uso: Decimal | None
    nivel: str | None
    tarjetas_con_intereses: list


def resumir_deudas(hogar):
    """RF-DEU-03, RN-08 y RN-09 con las cuentas activas del hogar."""
    cuentas = Cuenta.objects.del_hogar(hogar).filter(activo=True)
    tarjetas = list(cuentas.filter(tipo=Cuenta.Tipo.CREDITO))
    creditos = list(cuentas.filter(tipo=Cuenta.Tipo.PRESTAMO))
    uso = uso_de_credito(
        TarjetaCredito(saldo=t.saldo_actual, linea=t.linea_credito or CERO) for t in tarjetas
    )
    return ResumenDeudas(
        total_tarjetas=sum((max(CERO, t.saldo_actual) for t in tarjetas), CERO),
        total_creditos=sum((max(CERO, c.saldo_actual) for c in creditos), CERO),
        mensualidades=sum((c.mensualidad or CERO for c in creditos), CERO),
        uso=uso,
        nivel=None if uso is None else nivel_de_uso(uso),
        tarjetas_con_intereses=[t.nombre for t in tarjetas if t.paga_total_mensual is False],
    )
