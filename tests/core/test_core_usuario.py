import pytest
from django.contrib.auth import authenticate, get_user_model
from django.db import IntegrityError

from apps.core.models import Hogar, Membresia

pytestmark = pytest.mark.django_db


def test_modelo_de_usuario_es_el_personalizado():
    assert get_user_model()._meta.label == "core.Usuario"


def test_crear_usuario_normaliza_email_a_minusculas():
    usuario = get_user_model().objects.create_user(
        email="  Julio@Example.COM ", password="clave-segura-123"
    )

    assert usuario.email == "julio@example.com"
    assert usuario.check_password("clave-segura-123")
    assert not usuario.is_staff


def test_email_sin_distinguir_mayusculas_es_unico():
    Usuario = get_user_model()
    Usuario.objects.create_user(email="julio@example.com", password="x-clave-123")

    with pytest.raises(IntegrityError):
        Usuario.objects.create_user(email="JULIO@example.com", password="x-clave-123")


def test_login_ignora_mayusculas_del_email():
    get_user_model().objects.create_user(email="julio@example.com", password="clave-segura-123")

    assert authenticate(username="Julio@Example.com", password="clave-segura-123") is not None


def test_email_obligatorio():
    with pytest.raises(ValueError, match="email"):
        get_user_model().objects.create_user(email="", password="x")


def test_superusuario():
    admin = get_user_model().objects.create_superuser(email="a@example.com", password="clave-123-x")

    assert admin.is_staff and admin.is_superuser


def test_membresia_unica_por_hogar_y_usuario():
    usuario = get_user_model().objects.create_user(email="j@example.com", password="clave-123-x")
    hogar = Hogar.objects.create(nombre="Familia")
    Membresia.objects.create(hogar=hogar, usuario=usuario)

    assert hogar.moneda == "MXN"
    assert hogar.zona_horaria == "America/Monterrey"
    with pytest.raises(IntegrityError):
        Membresia.objects.create(hogar=hogar, usuario=usuario)


def test_admin_de_usuarios_carga(client):
    admin = get_user_model().objects.create_superuser(email="a@example.com", password="clave-123-x")
    client.force_login(admin)

    assert client.get("/admin/core/usuario/").status_code == 200
    assert client.get("/admin/core/usuario/add/").status_code == 200
    assert client.get("/admin/core/hogar/").status_code == 200
