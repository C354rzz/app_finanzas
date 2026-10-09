import pytest
from django.utils import timezone

from apps.catalogos.models import Persona

pytestmark = pytest.mark.django_db


def test_inicio_lleva_al_tablero_del_mes_actual(cliente):
    hoy = timezone.localdate()

    assert cliente.get("/").url == f"/tablero/{hoy.year}/{hoy.month}/"


def test_tablero_muestra_resumen_y_categorias(cliente, plantilla_excel):
    contenido = cliente.get("/tablero/2026/10/").content.decode()

    for texto in (
        "Octubre 2026",
        "$32,977.52",
        "$29,235.00",
        "$350,820.00",
        "Comida",
        "¡Felicidades!",
    ):
        assert texto in contenido


def test_tablero_muestra_alertas_de_tarjetas(cliente, catalogo):
    assert "96.32%" in cliente.get("/tablero/2026/10/").content.decode()


def test_filtro_por_domicilio(cliente, catalogo):
    respuesta = cliente.get("/tablero/2026/10/", {"domicilio": catalogo.fidel.pk})

    assert respuesta.context["tablero"].filtrado


def test_filtro_con_id_de_otro_hogar_se_ignora(cliente, catalogo, otro_hogar):
    ajena = Persona.objects.create(hogar=otro_hogar, nombre="Ajena")

    respuesta = cliente.get("/tablero/2026/10/", {"persona": ajena.pk})

    assert respuesta.status_code == 200
    assert not respuesta.context["tablero"].filtrado


def test_mes_invalido_da_404(cliente):
    assert cliente.get("/tablero/2026/0/").status_code == 404


def test_tablero_requiere_sesion(client):
    assert client.get("/tablero/2026/10/").status_code == 302
