import pytest
from django.contrib.auth import get_user_model

from apps.core.servicios import crear_hogar


@pytest.fixture
def usuario(db):
    return get_user_model().objects.create_user(
        email="julio@example.com", password="clave-segura-123"
    )


@pytest.fixture
def hogar(usuario):
    return crear_hogar("Familia Prueba", usuario)


@pytest.fixture
def otro_hogar(db):
    otro = get_user_model().objects.create_user(email="otro@example.com", password="clave-123-x")
    return crear_hogar("Otra Familia", otro)
