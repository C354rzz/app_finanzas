"""Mensajes de las hojas "Metas de Ahorro" y "Deudas" del Excel."""

from apps.calculos.deudas import NIVEL_BUENO, NIVEL_CUIDADO, NIVEL_RIESGO
from apps.presupuesto.mensajes import ALERTA, BIEN, CUIDADO


def mensaje_metas(disponible, total_metas):
    if disponible < 0:
        return ALERTA, (
            "⛔ ¡Tus gastos son mayores a tus ingresos! Recorta gastos para retomar tus metas "
            "de ahorro."
        )
    if disponible > total_metas:
        return BIEN, (
            "👏 ¡Felicidades! Tienes suficiente al final de mes para lograr tus metas de ahorro."
        )
    return CUIDADO, (
        "⚠️ Parece que lo disponible del mes no es suficiente para lograr tus metas de ahorro."
    )


MENSAJES_USO = {
    NIVEL_BUENO: "👏¡Buen nivel de uso de tus tarjetas!",
    NIVEL_CUIDADO: (
        "⚠️ Cuidado con el uso de tus tarjetas. Puede ser buena idea que adelantes pagos de "
        "tus mensualidades."
    ),
    NIVEL_RIESGO: "⛔ Usas demasiado tus tarjetas, considera disminuir tus gastos.",
}


def mensaje_uso(nivel):
    return MENSAJES_USO.get(nivel, "")


def mensaje_tarjeta(paga_total_mensual):
    if paga_total_mensual is None:
        return ""
    if paga_total_mensual:
        return "👏¡Bien! Esa es la mejor manera de usar tus tarjetas."
    return "⚠️ Cuidado, estás perdiendo dinero en intereses. Considera refinanciar tu tarjeta."
