from decimal import Decimal as D

import pytest

from apps.calculos.comun import redondear
from apps.catalogos.servicios import resumir_deudas

pytestmark = pytest.mark.django_db


def test_resumen_de_deudas(catalogo):
    r = resumir_deudas(catalogo.tarjeta.hogar)

    assert r.total_tarjetas == D("6839.01")
    assert r.total_creditos == D("38679.72")
    assert r.mensualidades == D("1500")
    assert redondear(r.uso, 4) == D("0.9632")
    assert r.nivel == "riesgo"
    assert r.tarjetas_con_intereses == ["Tarjeta Oro"]


def test_sin_tarjetas_no_hay_uso(hogar):
    r = resumir_deudas(hogar)

    assert (r.uso, r.nivel, r.total_tarjetas) == (None, None, 0)


def test_cuentas_inactivas_no_cuentan(catalogo):
    catalogo.tarjeta.activo = False
    catalogo.tarjeta.save()

    r = resumir_deudas(catalogo.tarjeta.hogar)

    assert r.total_tarjetas == 0
    assert r.tarjetas_con_intereses == []
