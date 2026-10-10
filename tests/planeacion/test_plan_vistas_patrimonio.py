from decimal import Decimal as D

import pytest

from apps.catalogos.models import Domicilio
from apps.planeacion.models import Activo

pytestmark = pytest.mark.django_db
HTMX = {"HX-Request": "true"}


def datos_activo(**campos):
    datos = {
        "tipo": "auto",
        "nombre": "Auto familiar",
        "valor_actual": "150000",
        "fecha_valuacion": "2026-10-01",
        "activo": "on",
    }
    datos.update(campos)
    return datos


def test_patrimonio_neto_del_excel(cliente, catalogo, hogar):
    for nombre, valor in [("Casa", "2400000"), ("Auto", "150000"), ("Ahorro", "43519.94")]:
        Activo.objects.create(hogar=hogar, nombre=nombre, valor_actual=D(valor))

    contenido = cliente.get("/planeacion/patrimonio/").content.decode()

    for texto in ("$2,593,519.94", "$38,679.72", "$6,839.01", "$2,548,001.21"):
        assert texto in contenido


def test_pantalla_sin_activos(cliente):
    assert "Aún no registras activos" in cliente.get("/planeacion/patrimonio/").content.decode()


def test_crear_activo(cliente, hogar):
    respuesta = cliente.post("/planeacion/patrimonio/nuevo/", datos_activo(), headers=HTMX)

    assert respuesta.status_code == 204
    assert Activo.objects.get().hogar == hogar


def test_valor_negativo_es_error(cliente, hogar):
    respuesta = cliente.post(
        "/planeacion/patrimonio/nuevo/", datos_activo(valor_actual="-1"), headers=HTMX
    )

    assert "valor_actual" in respuesta.context["formulario"].errors


def test_domicilio_de_otro_hogar_es_error(cliente, otro_hogar):
    ajeno = Domicilio.objects.create(hogar=otro_hogar, alias="Ajeno")

    respuesta = cliente.post(
        "/planeacion/patrimonio/nuevo/", datos_activo(domicilio=ajeno.pk), headers=HTMX
    )

    assert "domicilio" in respuesta.context["formulario"].errors


def test_editar_y_eliminar_activo(cliente, hogar):
    activo = Activo.objects.create(hogar=hogar, nombre="Auto", valor_actual=D("1"))

    cliente.post(f"/planeacion/patrimonio/{activo.pk}/", datos_activo(), headers=HTMX)
    activo.refresh_from_db()
    assert activo.valor_actual == D("150000")

    assert (
        cliente.post(f"/planeacion/patrimonio/{activo.pk}/eliminar/", headers=HTMX).status_code
        == 204
    )
    assert not Activo.objects.exists()


def test_activo_de_otro_hogar_da_404(cliente, otro_hogar):
    ajeno = Activo.objects.create(hogar=otro_hogar, nombre="Ajeno", valor_actual=D("1"))

    assert cliente.get(f"/planeacion/patrimonio/{ajeno.pk}/").status_code == 404
    assert cliente.post(f"/planeacion/patrimonio/{ajeno.pk}/eliminar/").status_code == 404


def test_mas_enlaza_al_patrimonio(cliente):
    assert "/planeacion/patrimonio/" in cliente.get("/catalogos/").content.decode()
