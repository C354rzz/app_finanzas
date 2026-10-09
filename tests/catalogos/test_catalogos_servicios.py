from decimal import Decimal as D

import pytest

from apps.calculos.comun import redondear
from apps.catalogos.models import Cuenta, TasaMercado
from apps.catalogos.servicios import resumir_deudas, tasa_sugerida

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


def test_tasa_sugerida(hogar):
    TasaMercado.objects.create(
        institucion="Banco Demo", producto="Clásica", tasa_promedio=D("0.45")
    )
    credito = Cuenta.Tipo.CREDITO

    capturada = Cuenta(hogar=hogar, nombre="A", tipo=credito, tasa_anual=D("0.30"))
    sin_tasa = Cuenta(
        hogar=hogar, nombre="B", tipo=credito, institucion="BANCO DEMO", producto="clásica"
    )
    debito = Cuenta(
        hogar=hogar,
        nombre="C",
        tipo=Cuenta.Tipo.DEBITO,
        institucion="Banco Demo",
        producto="Clásica",
    )
    desconocida = Cuenta(hogar=hogar, nombre="D", tipo=credito, institucion="Otro")

    assert tasa_sugerida(capturada) == D("0.30")
    assert tasa_sugerida(sin_tasa) == D("0.45")
    assert tasa_sugerida(debito) is None
    assert tasa_sugerida(desconocida) is None
