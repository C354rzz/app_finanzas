from decimal import Decimal as D

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError

from apps.catalogos.models import Categoria, Concepto, Cuenta, Domicilio, Persona, TasaMercado

pytestmark = pytest.mark.django_db


def test_del_hogar_aisla_los_datos(hogar, otro_hogar):
    Persona.objects.create(hogar=hogar, nombre="Monze")
    Persona.objects.create(hogar=otro_hogar, nombre="Ajeno")

    nombres = list(Persona.objects.del_hogar(hogar).values_list("nombre", flat=True))

    assert nombres == ["Monze"]


def test_nombre_unico_por_hogar_pero_repetible_entre_hogares(hogar, otro_hogar):
    Persona.objects.create(hogar=hogar, nombre="Fidel")
    Persona.objects.create(hogar=otro_hogar, nombre="Fidel")

    with pytest.raises(IntegrityError):
        Persona.objects.create(hogar=hogar, nombre="Fidel")


def test_concepto_con_categoria_de_otro_hogar_es_invalido(hogar, otro_hogar):
    categoria_ajena = Categoria.objects.create(hogar=otro_hogar, nombre="Casa")
    concepto = Concepto(hogar=hogar, categoria=categoria_ajena, nombre="Luz")

    with pytest.raises(ValidationError) as error:
        concepto.full_clean()

    assert "categoria" in error.value.message_dict


def test_concepto_con_persona_de_otro_hogar_es_invalido(hogar, otro_hogar):
    categoria = Categoria.objects.create(hogar=hogar, nombre="Casa")
    persona_ajena = Persona.objects.create(hogar=otro_hogar, nombre="Ajeno")
    concepto = Concepto(hogar=hogar, categoria=categoria, nombre="Luz", persona=persona_ajena)

    with pytest.raises(ValidationError) as error:
        concepto.full_clean()

    assert "persona" in error.value.message_dict


def test_concepto_valido_por_domicilio(hogar):
    casa = Categoria.objects.create(hogar=hogar, nombre="Casa")
    cedro = Domicilio.objects.create(hogar=hogar, alias="Casa Cedro")
    fidel = Domicilio.objects.create(hogar=hogar, alias="Casa Fidel")

    luz_cedro = Concepto(hogar=hogar, categoria=casa, nombre="Luz", domicilio=cedro)
    luz_cedro.full_clean()
    luz_cedro.save()
    Concepto.objects.create(hogar=hogar, categoria=casa, nombre="Luz", domicilio=fidel)

    assert Concepto.objects.del_hogar(hogar).filter(nombre="Luz").count() == 2


def test_concepto_duplicado_sin_domicilio_es_rechazado(hogar):
    casa = Categoria.objects.create(hogar=hogar, nombre="Casa")
    Concepto.objects.create(hogar=hogar, categoria=casa, nombre="Gas")

    with pytest.raises(IntegrityError):
        Concepto.objects.create(hogar=hogar, categoria=casa, nombre="Gas")


def test_cuenta_de_credito_con_campos_de_tarjeta(hogar):
    titular = Persona.objects.create(hogar=hogar, nombre="Julio")
    cuenta = Cuenta.objects.create(
        hogar=hogar,
        nombre="Stori",
        tipo=Cuenta.Tipo.CREDITO,
        institucion="Stori",
        producto="Stori Clásica",
        titular=titular,
        linea_credito=D("900"),
        saldo_actual=D("681.99"),
        dia_corte=13,
        dia_pago=3,
    )

    cuenta.full_clean()
    assert cuenta.saldo_actual == D("681.99")


def test_dia_de_corte_fuera_de_rango_es_invalido(hogar):
    cuenta = Cuenta(hogar=hogar, nombre="Hey", tipo=Cuenta.Tipo.CREDITO, dia_corte=32)

    with pytest.raises(ValidationError) as error:
        cuenta.full_clean()

    assert "dia_corte" in error.value.message_dict


def test_tasa_de_mercado_es_global():
    tasa = TasaMercado.objects.create(
        institucion="Stori", producto="Stori Clásica", tasa_promedio=D("1.0930")
    )

    assert not hasattr(tasa, "hogar")


def test_admin_de_catalogos_carga(client, usuario):
    usuario.is_staff = True
    usuario.is_superuser = True
    usuario.save()
    client.force_login(usuario)

    for modelo in ["persona", "domicilio", "categoria", "concepto", "cuenta", "tasamercado"]:
        assert client.get(f"/admin/catalogos/{modelo}/").status_code == 200, modelo


def test_borrar_hogar_con_conceptos_borra_todo(hogar):
    casa = Categoria.objects.create(hogar=hogar, nombre="Casa")
    Concepto.objects.create(hogar=hogar, categoria=casa, nombre="Luz")

    hogar.delete()

    assert not Concepto.objects.filter(nombre="Luz").exists()
    assert not Categoria.objects.filter(pk=casa.pk).exists()


def test_no_se_puede_borrar_una_categoria_con_conceptos(hogar):
    from django.db.models import RestrictedError

    casa = Categoria.objects.create(hogar=hogar, nombre="Casa")
    Concepto.objects.create(hogar=hogar, categoria=casa, nombre="Luz")

    with pytest.raises(RestrictedError):
        casa.delete()
