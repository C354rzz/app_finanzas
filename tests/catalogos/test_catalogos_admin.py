import pytest
from django.urls import reverse

from apps.catalogos.models import Categoria, Concepto

pytestmark = pytest.mark.django_db


def test_formulario_de_concepto_agrupa_los_valores_sugeridos(admin_client):
    respuesta = admin_client.get(reverse("admin:catalogos_concepto_add"))

    contenido = respuesta.content.decode()
    assert "Valores sugeridos (opcional)" in contenido
    assert "Persona por defecto" in contenido
    assert "Cuenta por defecto" in contenido
    assert "Domicilio por defecto" in contenido


def test_concepto_se_guarda_sin_valores_sugeridos(admin_client, hogar):
    transporte = Categoria.objects.create(hogar=hogar, nombre="Transporte")

    respuesta = admin_client.post(
        reverse("admin:catalogos_concepto_add"),
        {"hogar": hogar.pk, "categoria": transporte.pk, "nombre": "Gasolina", "activo": "on"},
    )

    assert respuesta.status_code == 302
    gasolina = Concepto.objects.get(nombre="Gasolina")
    assert (gasolina.persona, gasolina.cuenta, gasolina.domicilio) == (None, None, None)
