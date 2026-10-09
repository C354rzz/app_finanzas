"""Mensajes del Excel (hojas Presupuesto y Mis Finanzas), con rangos para cualquier %."""

from decimal import Decimal

BIEN, CUIDADO, ALERTA = "bien", "cuidado", "alerta"

# (desde qué % aplica, mensaje); se evalúan de mayor a menor.
MENSAJES_AHORRO = [
    (
        Decimal("0.25"),
        "¡Genial! Ahora toca hacerlo crecer. Revisa las mejores oportunidades de inversión 📈",
    ),
    (Decimal("0.20"), "¡Muy bien, este es un ahorro ideal! 🎯"),
    (Decimal("0.15"), "¡Buena meta de ahorro! Tu yo del futuro te lo agradecerá 💰"),
    (Decimal("0.10"), "Este es un buen porcentaje. ¡Ten disciplina para lograrlo! ✏️"),
    (Decimal("0"), "Podrías ahorrar más, evalúa tus gastos y mejora tus finanzas. ¡Tú puedes! 💪"),
]


def mensaje_ahorro(porcentaje):
    for desde, mensaje in MENSAJES_AHORRO:
        if porcentaje >= desde:
            return mensaje
    return MENSAJES_AHORRO[-1][1]


def mensaje_disponible(disponible, meta):
    if disponible >= meta:
        return BIEN, (
            "👏¡Felicidades!, tu disponible al final del mes es suficiente para lograr "
            "tus metas de ahorro."
        )
    if disponible > 0:
        return CUIDADO, (
            "⚠️Cuidado, lo que te resta al final del mes no es suficiente para llegar a "
            "tu meta de ahorro mensual."
        )
    return ALERTA, (
        "⛔¡Tus gastos son mayores a tus ingresos! Es momento de evaluar qué gastos hay que evitar."
    )


def mensaje_recorte(recorte_necesario):
    if recorte_necesario is None:
        return "👏¡Bien! Puedes lograr tus metas de ahorro y hasta darte un gustito 🐜"
    return (
        "⚠️Considera recortar gastos para lograr tus metas de ahorro "
        "(tip: comienza con tus gastos hormiga)."
    )
