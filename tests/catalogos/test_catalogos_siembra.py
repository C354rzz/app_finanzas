import pytest
from django.core.management import CommandError, call_command

from apps.catalogos.models import Categoria
from apps.catalogos.servicios import CATEGORIAS_INICIALES, sembrar_catalogos
from apps.core.models import Membresia

pytestmark = pytest.mark.django_db

NOMBRES_EXCEL = [
    "Casa", "Comida", "Familia", "Transporte", "Viajes", "Deudas", "Salud",
    "Suscripciones", "Gastos anuales", "Cuidado personal", "Entretenimiento", "Otros",
]  # fmt: skip


def test_siembra_las_12_categorias_del_excel_en_orden(hogar):
    creadas = sembrar_catalogos(hogar)

    assert creadas == 12
    assert [n for n, _ in CATEGORIAS_INICIALES] == NOMBRES_EXCEL
    nombres = list(Categoria.objects.del_hogar(hogar).values_list("nombre", flat=True))
    assert nombres == NOMBRES_EXCEL


def test_siembra_es_idempotente(hogar):
    sembrar_catalogos(hogar)

    assert sembrar_catalogos(hogar) == 0
    assert Categoria.objects.del_hogar(hogar).count() == 12


def test_comando_crea_hogar_y_siembra(usuario):
    call_command("crear_hogar", nombre="Familia Armijo", email="JULIO@example.com")

    membresia = Membresia.objects.get(usuario=usuario)
    assert membresia.hogar.nombre == "Familia Armijo"
    assert Categoria.objects.del_hogar(membresia.hogar).count() == 12


def test_comando_falla_si_el_usuario_no_existe(db):
    with pytest.raises(CommandError, match="No existe"):
        call_command("crear_hogar", nombre="X", email="nadie@example.com")


def test_comando_falla_si_el_usuario_ya_tiene_hogar(usuario, hogar):
    with pytest.raises(CommandError, match="ya pertenece"):
        call_command("crear_hogar", nombre="Otro", email="julio@example.com")
