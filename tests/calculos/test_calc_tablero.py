from decimal import Decimal as D

import pytest
from apps.calculos.tablero import AMBAR, ROJO, VERDE, avance, distribucion, semaforo

from apps.calculos.comun import CERO, redondear


def test_avance():
    assert avance(D("1200"), D("2400")) == D("0.5")
    assert avance(D("10"), D("0")) is None


@pytest.mark.parametrize(
    ("gastado", "color"), [("1919", VERDE), ("1920", AMBAR), ("2400", AMBAR), ("2400.01", ROJO)]
)
def test_semaforo_con_presupuesto_de_2400(gastado, color):
    assert semaforo(D(gastado), D("2400")) == color


def test_semaforo_sin_presupuesto():
    assert semaforo(D("10"), D("0")) == ROJO
    assert semaforo(D("0"), D("0")) == VERDE


def test_distribucion_sobre_el_total():
    resultado = distribucion({"Comida": D("10600"), "Resto": D("18635")})

    assert redondear(resultado["Comida"], 4) == D("0.3626")
    assert redondear(sum(resultado.values()), 10) == D("1")


def test_distribucion_sin_total():
    assert distribucion({"Comida": CERO}) == {"Comida": CERO}
