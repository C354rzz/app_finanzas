import pytest

from apps.catalogos.models import Categoria, Concepto, Persona
from apps.core.formularios import FormularioDeHogar

pytestmark = pytest.mark.django_db


class FormularioPersona(FormularioDeHogar):
    class Meta:
        model = Persona
        fields = ["nombre"]


class FormularioConcepto(FormularioDeHogar):
    class Meta:
        model = Concepto
        fields = ["categoria", "nombre", "persona"]


class FormularioNombreDeConcepto(FormularioDeHogar):
    class Meta:
        model = Concepto
        fields = ["nombre"]


def test_nombre_repetido_en_el_hogar_es_error_del_formulario(hogar):
    Persona.objects.create(hogar=hogar, nombre="Monze")

    formulario = FormularioPersona(data={"nombre": "Monze"}, hogar=hogar)

    assert not formulario.is_valid()
    assert "__all__" in formulario.errors


def test_mismo_nombre_en_otro_hogar_es_valido(hogar, otro_hogar):
    Persona.objects.create(hogar=otro_hogar, nombre="Monze")

    formulario = FormularioPersona(data={"nombre": "Monze"}, hogar=hogar)

    assert formulario.is_valid(), formulario.errors
    assert formulario.save().hogar == hogar


def test_listas_solo_muestran_registros_activos_del_hogar(hogar, otro_hogar):
    casa = Categoria.objects.create(hogar=hogar, nombre="Casa")
    Categoria.objects.create(hogar=otro_hogar, nombre="Casa")
    Categoria.objects.create(hogar=hogar, nombre="Vieja", activo=False)

    formulario = FormularioConcepto(hogar=hogar)

    assert list(formulario.fields["categoria"].queryset) == [casa]


def test_al_editar_conserva_el_valor_actual_aunque_este_inactivo(hogar):
    casa = Categoria.objects.create(hogar=hogar, nombre="Casa")
    abuela = Persona.objects.create(hogar=hogar, nombre="Abuela", activo=False)
    concepto = Concepto.objects.create(
        hogar=hogar, categoria=casa, nombre="Medicinas", persona=abuela
    )

    formulario = FormularioConcepto(instance=concepto, hogar=hogar)

    assert abuela in formulario.fields["persona"].queryset
    assert abuela not in FormularioConcepto(hogar=hogar).fields["persona"].queryset


def test_un_id_de_otro_hogar_es_rechazado(hogar, otro_hogar):
    ajena = Categoria.objects.create(hogar=otro_hogar, nombre="Casa")

    formulario = FormularioConcepto(data={"categoria": ajena.pk, "nombre": "Luz"}, hogar=hogar)

    assert not formulario.is_valid()
    assert "categoria" in formulario.errors


def test_error_de_un_campo_fuera_del_formulario_se_muestra_como_general(hogar, otro_hogar):
    ajena = Categoria.objects.create(hogar=otro_hogar, nombre="Casa")

    formulario = FormularioNombreDeConcepto(
        data={"nombre": "Luz"}, instance=Concepto(categoria=ajena), hogar=hogar
    )

    assert not formulario.is_valid()
    assert "Pertenece a otro hogar." in str(formulario.non_field_errors())
