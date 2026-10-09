import pytest


@pytest.mark.django_db
def test_salud_responde_ok(client):
    respuesta = client.get("/salud/")

    assert respuesta.status_code == 200
    assert respuesta.json() == {"estado": "ok"}
