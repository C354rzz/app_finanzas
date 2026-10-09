from decimal import Decimal as D

import pytest

from apps.catalogos.models import Concepto, Cuenta, Domicilio, Persona, TasaMercado
from apps.movimientos.models import Movimiento
from apps.movimientos.servicios import guardar_movimiento
from apps.presupuesto.models import PlantillaGasto
from apps.presupuesto.servicios import obtener_plantilla

pytestmark = pytest.mark.django_db
HTMX = {"HX-Request": "true"}


def test_indice_lista_los_catalogos(cliente):
    contenido = cliente.get("/catalogos/").content.decode()

    for titulo in ("Personas", "Domicilios", "Categorías", "Conceptos", "Cuentas"):
        assert titulo in contenido


def test_lista_solo_muestra_registros_del_hogar(cliente, catalogo, otro_hogar):
    Persona.objects.create(hogar=otro_hogar, nombre="Ajena")

    contenido = cliente.get("/catalogos/personas/").content.decode()

    assert "Monze" in contenido
    assert "Ajena" not in contenido


def test_crear_persona(cliente, hogar):
    respuesta = cliente.post(
        "/catalogos/personas/nuevo/", {"nombre": "Fidel", "activo": "on"}, headers=HTMX
    )

    assert respuesta.status_code == 204
    assert Persona.objects.get(nombre="Fidel").hogar == hogar


def test_nombre_repetido_es_error_del_formulario(cliente, catalogo):
    respuesta = cliente.post(
        "/catalogos/personas/nuevo/", {"nombre": "Monze", "activo": "on"}, headers=HTMX
    )

    assert respuesta.status_code == 200
    assert "__all__" in respuesta.context["formulario"].errors


def test_editar_domicilio(cliente, catalogo):
    respuesta = cliente.post(
        f"/catalogos/domicilios/{catalogo.fidel.pk}/",
        {"alias": "Casa Fidel", "direccion": "Calle Ficticia 1", "activo": "on"},
        headers=HTMX,
    )

    assert respuesta.status_code == 204
    assert Domicilio.objects.get(pk=catalogo.fidel.pk).direccion == "Calle Ficticia 1"


def test_formulario_de_concepto_agrupa_valores_sugeridos(cliente, catalogo):
    contenido = cliente.get("/catalogos/conceptos/nuevo/", headers=HTMX).content.decode()

    assert "Valores sugeridos (opcional)" in contenido
    assert "Persona por defecto" in contenido


def test_crear_concepto_sin_valores_sugeridos(cliente, catalogo):
    respuesta = cliente.post(
        "/catalogos/conceptos/nuevo/",
        {"categoria": catalogo.categorias["Transporte"].pk, "nombre": "Casetas", "activo": "on"},
        headers=HTMX,
    )

    assert respuesta.status_code == 204
    casetas = Concepto.objects.get(nombre="Casetas")
    assert (casetas.persona, casetas.cuenta, casetas.domicilio) == (None, None, None)


def test_eliminar_sin_uso_borra(cliente, hogar):
    temporal = Persona.objects.create(hogar=hogar, nombre="Temporal")

    respuesta = cliente.post(f"/catalogos/personas/{temporal.pk}/eliminar/", headers=HTMX)

    assert respuesta.status_code == 204
    assert not Persona.objects.filter(pk=temporal.pk).exists()


def test_eliminar_cuenta_con_movimientos_la_desactiva(cliente, catalogo):
    guardar_movimiento(
        Movimiento(
            hogar=catalogo.efectivo.hogar,
            tipo=Movimiento.Tipo.GASTO,
            monto=D("10"),
            concepto=catalogo.gasolina,
            cuenta=catalogo.efectivo,
        )
    )

    cliente.post(f"/catalogos/cuentas/{catalogo.efectivo.pk}/eliminar/", headers=HTMX)

    catalogo.efectivo.refresh_from_db()
    assert catalogo.efectivo.activo is False


def test_eliminar_concepto_del_presupuesto_lo_desactiva(cliente, catalogo, hogar):
    PlantillaGasto.objects.create(
        hogar=hogar, plantilla=obtener_plantilla(hogar), concepto=catalogo.gasolina, monto=D("1")
    )

    cliente.post(f"/catalogos/conceptos/{catalogo.gasolina.pk}/eliminar/", headers=HTMX)

    catalogo.gasolina.refresh_from_db()
    assert catalogo.gasolina.activo is False


def test_registro_de_otro_hogar_da_404(cliente, otro_hogar):
    ajena = Persona.objects.create(hogar=otro_hogar, nombre="Ajena")

    assert cliente.get(f"/catalogos/personas/{ajena.pk}/").status_code == 404
    assert cliente.post(f"/catalogos/personas/{ajena.pk}/eliminar/").status_code == 404
    assert Persona.objects.filter(pk=ajena.pk).exists()


def test_catalogo_desconocido_da_404(cliente):
    assert cliente.get("/catalogos/otro/").status_code == 404


def test_cuentas_muestran_la_tasa_de_mercado(cliente, hogar):
    TasaMercado.objects.create(
        institucion="Banco Demo", producto="Clásica", tasa_promedio=D("0.4500")
    )
    Cuenta.objects.create(
        hogar=hogar,
        nombre="Demo",
        tipo=Cuenta.Tipo.CREDITO,
        institucion="banco demo",
        producto="clásica",
    )

    contenido = cliente.get("/catalogos/cuentas/").content.decode()

    assert "45.00% (promedio del mercado)" in contenido
