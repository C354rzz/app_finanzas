import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.http import HttpResponse

from apps.core.middleware import HogarMiddleware
from apps.core.models import Membresia
from apps.core.servicios import crear_hogar


def _procesar(request):
    HogarMiddleware(lambda r: HttpResponse())(request)
    return request


def test_crear_hogar_crea_membresia_admin(usuario):
    hogar = crear_hogar("Familia Armijo", usuario)

    membresia = Membresia.objects.get(hogar=hogar, usuario=usuario)
    assert membresia.rol == Membresia.Rol.ADMIN
    assert hogar.nombre == "Familia Armijo"


def test_middleware_asigna_el_hogar_del_usuario(rf, usuario, hogar, otro_hogar):
    request = rf.get("/")
    request.user = usuario

    assert _procesar(request).hogar == hogar


def test_middleware_usuario_sin_hogar(rf, db):
    request = rf.get("/")
    request.user = get_user_model().objects.create_user(email="s@example.com", password="x-12345")

    assert _procesar(request).hogar is None


def test_middleware_anonimo(rf):
    request = rf.get("/")
    request.user = AnonymousUser()

    assert _procesar(request).hogar is None


@pytest.mark.django_db
def test_middleware_instalado_en_peticiones_reales(client, usuario, hogar):
    client.force_login(usuario)

    respuesta = client.get("/salud/")

    assert respuesta.wsgi_request.hogar == hogar
