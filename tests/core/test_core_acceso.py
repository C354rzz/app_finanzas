import pytest

pytestmark = pytest.mark.django_db


def test_sin_sesion_redirige_al_login(client):
    respuesta = client.get("/")

    assert respuesta.status_code == 302
    assert respuesta.url == "/entrar/?next=/"


def test_la_pantalla_de_entrada_pide_email_y_contrasena(client):
    respuesta = client.get("/entrar/")

    contenido = respuesta.content.decode()
    assert respuesta.status_code == 200
    assert "Email" in contenido
    assert 'type="password"' in contenido


def test_entra_con_el_email_en_mayusculas(client, hogar):
    respuesta = client.post(
        "/entrar/", {"username": "JULIO@Example.com", "password": "clave-segura-123"}
    )

    assert respuesta.status_code == 302
    assert respuesta.url == "/"
    assert "_auth_user_id" in client.session


def test_contrasena_incorrecta_no_entra(client, usuario):
    respuesta = client.post("/entrar/", {"username": "julio@example.com", "password": "otra"})

    assert respuesta.status_code == 200
    assert respuesta.context["form"].errors
    assert "_auth_user_id" not in client.session


def test_usuario_sin_hogar_ve_un_aviso(client, usuario):
    client.force_login(usuario)

    respuesta = client.get("/")

    assert respuesta.status_code == 403
    assert "no perteneces a ningún hogar" in respuesta.content.decode()


def test_inicio_muestra_la_navegacion(cliente):
    respuesta = cliente.get("/")

    assert respuesta.status_code == 200
    assert "Salir" in respuesta.content.decode()


def test_salir_cierra_la_sesion(cliente):
    respuesta = cliente.post("/salir/")

    assert respuesta.status_code == 302
    assert respuesta.url == "/entrar/"
    assert cliente.get("/").status_code == 302
