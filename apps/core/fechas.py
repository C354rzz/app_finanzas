"""Meses del calendario: rangos, navegación y nombres (el mes financiero es el calendario)."""

import calendar
from datetime import date

MESES = [
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
]  # fmt: skip
ANIO_MINIMO, ANIO_MAXIMO = 2000, 2100


def validar_mes(anio, mes):
    if not (1 <= mes <= 12 and ANIO_MINIMO <= anio <= ANIO_MAXIMO):
        raise ValueError(f"Mes fuera de rango: {anio}-{mes}")


def rango_del_mes(anio, mes):
    validar_mes(anio, mes)
    return date(anio, mes, 1), date(anio, mes, calendar.monthrange(anio, mes)[1])


def rango_del_anio(anio):
    validar_mes(anio, 1)
    return date(anio, 1, 1), date(anio, 12, 31)


def mes_anterior(anio, mes):
    return (anio - 1, 12) if mes == 1 else (anio, mes - 1)


def mes_siguiente(anio, mes):
    return (anio + 1, 1) if mes == 12 else (anio, mes + 1)


def nombre_mes(anio, mes):
    return f"{MESES[mes - 1].capitalize()} {anio}"
