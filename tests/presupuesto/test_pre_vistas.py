from decimal import Decimal as D

import pytest
from django.utils import timezone

from apps.presupuesto.models import PlantillaGasto, PlantillaIngreso
from apps.presupuesto.servicios import obtener_plantilla, obtener_presupuesto_mes, resumen_plantilla

pytestmark = pytest.mark.django_db
HTMX = {"HX-Request": "true"}


def gasto_de_plantilla(catalogo, monto="1400"):
    return {
        "concepto": catalogo.gasolina.pk,
        "monto": monto,
        "periodicidad": "mensual",
        "es_fijo": "on",
    }


def test_presupuesto_redirige_al_mes_actual(cliente):
    hoy = timezone.localdate()

    assert cliente.get("/presupuesto/").url == f"/presupuesto/{hoy.year}/{hoy.month}/"


def test_plantilla_muestra_el_resumen_del_excel(cliente, plantilla_excel):
    contenido = cliente.get("/presupuesto/plantilla/").content.decode()

    for valor in ("$32,977.52", "$29,235.00", "$3,742.52", "$1,648.88", "$2,739.00", "$91.30"):
        assert valor in contenido
    assert "Podrías ahorrar más" in contenido
    assert "¡Felicidades!" in contenido
    assert "N/A" in contenido


def test_mes_muestra_su_presupuesto(cliente, plantilla_excel):
    respuesta = cliente.get("/presupuesto/2026/10/")

    contenido = respuesta.content.decode()
    assert respuesta.status_code == 200
    assert "Octubre 2026" in contenido
    assert "$29,235.00" in contenido


def test_mes_invalido_da_404(cliente):
    assert cliente.get("/presupuesto/2026/13/").status_code == 404


def test_formulario_de_nuevo_renglon(cliente, catalogo):
    respuesta = cliente.get("/presupuesto/plantilla/ingreso/nuevo/", headers=HTMX)

    assert respuesta.status_code == 200
    assert 'name="nombre"' in respuesta.content.decode()


def test_agregar_gasto_a_la_plantilla(cliente, catalogo, hogar):
    respuesta = cliente.post(
        "/presupuesto/plantilla/gasto/nuevo/", gasto_de_plantilla(catalogo), headers=HTMX
    )

    assert respuesta.status_code == 204
    renglon = PlantillaGasto.objects.get()
    assert renglon.plantilla == obtener_plantilla(hogar)
    assert renglon.hogar == hogar
    assert renglon.es_fijo


def test_concepto_repetido_en_la_plantilla_es_error(cliente, catalogo):
    url = "/presupuesto/plantilla/gasto/nuevo/"
    cliente.post(url, gasto_de_plantilla(catalogo), headers=HTMX)

    respuesta = cliente.post(url, gasto_de_plantilla(catalogo, "1"), headers=HTMX)

    assert respuesta.status_code == 200
    assert "__all__" in respuesta.context["formulario"].errors
    assert PlantillaGasto.objects.count() == 1


def test_editar_renglon_del_mes_no_cambia_la_plantilla(cliente, plantilla_excel, hogar):
    renglon = obtener_presupuesto_mes(hogar, 2026, 10).gastos.first()

    respuesta = cliente.post(
        f"/presupuesto/renglon/mes/gasto/{renglon.pk}/",
        {"concepto": renglon.concepto_id, "monto_mensual": "1"},
        headers=HTMX,
    )

    assert respuesta.status_code == 204
    renglon.refresh_from_db()
    assert renglon.monto_mensual == D("1")
    assert resumen_plantilla(plantilla_excel).gastos_totales == D("29235")


def test_eliminar_renglon(cliente, catalogo, hogar):
    renglon = PlantillaGasto.objects.create(
        hogar=hogar, plantilla=obtener_plantilla(hogar), concepto=catalogo.gasolina, monto=D("1")
    )

    respuesta = cliente.post(
        f"/presupuesto/renglon/plantilla/gasto/{renglon.pk}/eliminar/", headers=HTMX
    )

    assert respuesta.status_code == 204
    assert not PlantillaGasto.objects.exists()


def test_renglon_de_otro_hogar_da_404(cliente, otro_hogar):
    ajeno = PlantillaIngreso.objects.create(
        hogar=otro_hogar, plantilla=obtener_plantilla(otro_hogar), nombre="Ajeno", monto=D("1")
    )

    assert cliente.get(f"/presupuesto/renglon/plantilla/ingreso/{ajeno.pk}/").status_code == 404
    url_eliminar = f"/presupuesto/renglon/plantilla/ingreso/{ajeno.pk}/eliminar/"
    assert cliente.post(url_eliminar).status_code == 404
    assert PlantillaIngreso.objects.filter(pk=ajeno.pk).exists()


def test_clase_desconocida_da_404(cliente):
    assert cliente.get("/presupuesto/plantilla/otro/nuevo/").status_code == 404


def test_cambiar_el_porcentaje_de_ahorro(cliente, hogar):
    respuesta = cliente.post("/presupuesto/plantilla/porcentaje/", {"porcentaje": "10"})

    assert respuesta.status_code == 302
    assert obtener_plantilla(hogar).porcentaje_ahorro == D("0.10")


def test_porcentaje_fuera_de_rango_no_se_guarda(cliente, hogar):
    cliente.post("/presupuesto/plantilla/porcentaje/", {"porcentaje": "150"})

    assert obtener_plantilla(hogar).porcentaje_ahorro == D("0.05")


def test_porcentaje_del_mes_no_cambia_la_plantilla(cliente, hogar):
    cliente.post("/presupuesto/2026/10/porcentaje/", {"porcentaje": "20"})

    assert obtener_presupuesto_mes(hogar, 2026, 10).porcentaje_ahorro == D("0.20")
    assert obtener_plantilla(hogar).porcentaje_ahorro == D("0.05")


def test_resincronizar_el_mes(cliente, plantilla_excel, hogar):
    octubre = obtener_presupuesto_mes(hogar, 2026, 10)
    octubre.gastos.all().delete()

    respuesta = cliente.post("/presupuesto/2026/10/resincronizar/")

    assert respuesta.status_code == 302
    assert octubre.gastos.count() == 28
