from datetime import date

import pytest

from apps.core.fechas import (
    mes_anterior,
    mes_siguiente,
    nombre_mes,
    rango_del_anio,
    rango_del_mes,
    validar_mes,
)


def test_rango_del_mes_incluye_el_ultimo_dia():
    assert rango_del_mes(2026, 10) == (date(2026, 10, 1), date(2026, 10, 31))
    assert rango_del_mes(2028, 2) == (date(2028, 2, 1), date(2028, 2, 29))


def test_rango_del_anio():
    assert rango_del_anio(2026) == (date(2026, 1, 1), date(2026, 12, 31))


def test_navegacion_entre_anios():
    assert mes_anterior(2026, 1) == (2025, 12)
    assert mes_siguiente(2026, 12) == (2027, 1)
    assert mes_siguiente(2026, 10) == (2026, 11)


def test_nombre_del_mes():
    assert nombre_mes(2026, 10) == "Octubre 2026"


@pytest.mark.parametrize(("anio", "mes"), [(2026, 0), (2026, 13), (1999, 5), (2101, 1)])
def test_mes_fuera_de_rango(anio, mes):
    with pytest.raises(ValueError):
        validar_mes(anio, mes)
