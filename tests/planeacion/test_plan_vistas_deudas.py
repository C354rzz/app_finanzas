import pytest

from apps.catalogos.models import Cuenta

pytestmark = pytest.mark.django_db
HTMX = {"HX-Request": "true"}
CAPTURA = "/movimientos/capturar/pago_deuda/"


def test_pantalla_de_deudas(cliente, catalogo):
    contenido = cliente.get("/planeacion/deudas/").content.decode()

    for texto in ("Tarjeta Oro", "96.32%", "⚠️ Cuidado, estás perdiendo dinero", "Préstamo auto",
                  "5.96%", "$45,518.73", "Registrar pago"):  # fmt: skip
        assert texto in contenido
    assert f"cuenta_destino={catalogo.tarjeta.pk}" in contenido


def test_pantalla_sin_deudas(cliente):
    contenido = cliente.get("/planeacion/deudas/").content.decode()

    assert "No tienes tarjetas de crédito registradas." in contenido
    assert "No tienes créditos registrados." in contenido


def test_registrar_pago_precarga_la_tarjeta(cliente, catalogo):
    respuesta = cliente.get(CAPTURA, {"cuenta_destino": catalogo.tarjeta.pk}, headers=HTMX)

    assert respuesta.context["formulario"]["cuenta_destino"].value() == catalogo.tarjeta.pk


def test_cuenta_destino_ajena_o_invalida_se_ignora(cliente, catalogo, otro_hogar):
    ajena = Cuenta.objects.create(hogar=otro_hogar, nombre="Ajena", tipo=Cuenta.Tipo.CREDITO)

    for valor in (ajena.pk, catalogo.efectivo.pk, "abc"):
        respuesta = cliente.get(CAPTURA, {"cuenta_destino": valor}, headers=HTMX)
        assert respuesta.context["formulario"]["cuenta_destino"].value() is None


def test_mas_enlaza_a_deudas(cliente):
    assert "/planeacion/deudas/" in cliente.get("/catalogos/").content.decode()
