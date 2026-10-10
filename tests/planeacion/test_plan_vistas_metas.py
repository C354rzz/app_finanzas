from datetime import date
from decimal import Decimal as D

import pytest

from apps.catalogos.models import Cuenta
from apps.planeacion.models import MetaAhorro

pytestmark = pytest.mark.django_db
HTMX = {"HX-Request": "true"}


def datos_meta(**campos):
    datos = {
        "tipo": "regalo",
        "nombre": "Regalo",
        "monto_objetivo": "20000",
        "ahorro_actual": "0",
        "meses": "12",
        "tasa_anual": "10",
        "fecha_inicio": "2026-10-01",
        "activa": "on",
    }
    datos.update(campos)
    return datos


def crear_meta(hogar, nombre="Regalo", monto="20000"):
    return MetaAhorro.objects.create(
        hogar=hogar, nombre=nombre, monto_objetivo=D(monto), fecha_inicio=date(2026, 10, 1)
    )


def test_pantalla_de_metas_con_los_valores_del_excel(cliente, plantilla_excel, hogar):
    crear_meta(hogar)
    crear_meta(hogar, "Vacaciones", "45000")

    contenido = cliente.get("/planeacion/metas/").content.decode()

    for texto in ("$1,591.65", "$3,581.21", "$5,172.87", "15.69%", "⚠️ Parece que lo disponible"):
        assert texto in contenido


def test_pantalla_sin_metas(cliente):
    assert "Aún no tienes metas de ahorro" in cliente.get("/planeacion/metas/").content.decode()


def test_crear_meta(cliente, hogar):
    respuesta = cliente.post("/planeacion/metas/nueva/", datos_meta(), headers=HTMX)

    assert respuesta.status_code == 204
    meta = MetaAhorro.objects.get()
    assert (meta.hogar, meta.tasa_anual, meta.meses) == (hogar, D("0.10"), 12)


def test_editar_muestra_la_tasa_en_porcentaje(cliente, hogar):
    meta = crear_meta(hogar)

    respuesta = cliente.get(f"/planeacion/metas/{meta.pk}/", headers=HTMX)

    assert 'value="10.00"' in respuesta.content.decode()


def test_meses_cero_es_error(cliente, hogar):
    respuesta = cliente.post("/planeacion/metas/nueva/", datos_meta(meses="0"), headers=HTMX)

    assert respuesta.status_code == 200
    assert "meses" in respuesta.context["formulario"].errors
    assert not MetaAhorro.objects.exists()


def test_cuenta_de_otro_hogar_es_error(cliente, otro_hogar):
    ajena = Cuenta.objects.create(hogar=otro_hogar, nombre="Ajena", tipo=Cuenta.Tipo.AHORRO)

    respuesta = cliente.post("/planeacion/metas/nueva/", datos_meta(cuenta=ajena.pk), headers=HTMX)

    assert "cuenta" in respuesta.context["formulario"].errors


def test_eliminar_meta(cliente, hogar):
    meta = crear_meta(hogar)

    respuesta = cliente.post(f"/planeacion/metas/{meta.pk}/eliminar/", headers=HTMX)

    assert respuesta.status_code == 204
    assert not MetaAhorro.objects.exists()


def test_meta_de_otro_hogar_da_404(cliente, otro_hogar):
    ajena = crear_meta(otro_hogar)

    assert cliente.get(f"/planeacion/metas/{ajena.pk}/").status_code == 404
    assert cliente.post(f"/planeacion/metas/{ajena.pk}/eliminar/").status_code == 404
    assert MetaAhorro.objects.filter(pk=ajena.pk).exists()


def test_mas_enlaza_a_las_metas(cliente):
    assert "/planeacion/metas/" in cliente.get("/catalogos/").content.decode()
