from decimal import Decimal as D
from types import SimpleNamespace

import pytest
from django.contrib.auth import get_user_model

from apps.catalogos.models import Categoria, Concepto, Cuenta, Domicilio, Persona
from apps.catalogos.servicios import sembrar_catalogos
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


@pytest.fixture
def cliente(client, usuario, hogar):
    """Cliente con sesión iniciada de un usuario que ya tiene hogar."""
    client.force_login(usuario)
    return client


@pytest.fixture
def catalogo(hogar):
    """Catálogo mínimo y ficticio de un hogar."""
    sembrar_catalogos(hogar)
    categorias = {c.nombre: c for c in Categoria.objects.del_hogar(hogar)}
    fidel = Domicilio.objects.create(hogar=hogar, alias="Casa Fidel")
    nomina = Cuenta.objects.create(hogar=hogar, nombre="Nómina", tipo=Cuenta.Tipo.DEBITO)
    return SimpleNamespace(
        categorias=categorias,
        monze=Persona.objects.create(hogar=hogar, nombre="Monze", parentesco="hija"),
        fidel=fidel,
        efectivo=Cuenta.objects.create(hogar=hogar, nombre="Efectivo", tipo=Cuenta.Tipo.EFECTIVO),
        nomina=nomina,
        tarjeta=Cuenta.objects.create(
            hogar=hogar,
            nombre="Tarjeta Oro",
            tipo=Cuenta.Tipo.CREDITO,
            linea_credito=D("7100"),
            saldo_actual=D("6839.01"),
            paga_total_mensual=False,
        ),
        prestamo=Cuenta.objects.create(
            hogar=hogar,
            nombre="Préstamo auto",
            tipo=Cuenta.Tipo.PRESTAMO,
            monto_inicial=D("41130"),
            mensualidad=D("1500"),
            saldo_actual=D("38679.72"),
        ),
        gasolina=Concepto.objects.create(
            hogar=hogar, categoria=categorias["Transporte"], nombre="Gasolina"
        ),
        recarga=Concepto.objects.create(
            hogar=hogar, categoria=categorias["Casa"], nombre="Recarga móvil"
        ),
        luz_fidel=Concepto.objects.create(
            hogar=hogar,
            categoria=categorias["Casa"],
            nombre="Luz",
            domicilio=fidel,
            cuenta=nomina,
            es_fijo=True,
        ),
    )
