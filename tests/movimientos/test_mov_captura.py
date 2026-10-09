from decimal import Decimal as D

import pytest

from apps.catalogos.models import Categoria, Concepto
from apps.movimientos.models import Movimiento

pytestmark = pytest.mark.django_db

URL = "/movimientos/capturar/{}/"
HTMX = {"HX-Request": "true"}


def gasto_minimo(concepto, monto="650"):
    return {
        "monto": monto,
        "concepto": concepto.pk,
        "fecha": "2026-10-09",
        "metodo_pago": "efectivo",
    }


def concepto_ajeno(otro_hogar):
    ajena = Categoria.objects.create(hogar=otro_hogar, nombre="Ajena")
    return Concepto.objects.create(hogar=otro_hogar, categoria=ajena, nombre="Concepto ajeno")


def test_captura_muestra_los_cuatro_tipos_y_solo_conceptos_del_hogar(cliente, catalogo, otro_hogar):
    concepto_ajeno(otro_hogar)

    respuesta = cliente.get(URL.format("gasto"), headers=HTMX)

    contenido = respuesta.content.decode()
    assert respuesta.status_code == 200
    for etiqueta in ("Gasto", "Ingreso", "Transferencia", "Pago de deuda"):
        assert etiqueta in contenido
    assert "Transporte › Gasolina" in contenido
    assert "Concepto ajeno" not in contenido


def test_gasto_rapido_con_monto_y_concepto(cliente, catalogo, usuario):
    respuesta = cliente.post(URL.format("gasto"), gasto_minimo(catalogo.gasolina), headers=HTMX)

    assert respuesta.status_code == 204
    assert respuesta["HX-Trigger"] == "datosActualizados"
    movimiento = Movimiento.objects.get()
    assert movimiento.categoria == catalogo.categorias["Transporte"]
    assert movimiento.descripcion == "Gasolina"
    assert movimiento.creado_por == usuario
    assert movimiento.hogar == catalogo.gasolina.hogar


def test_errores_se_muestran_en_el_modal(cliente, catalogo):
    respuesta = cliente.post(
        URL.format("gasto"), gasto_minimo(catalogo.gasolina, monto=""), headers=HTMX
    )

    assert respuesta.status_code == 200
    assert "monto" in respuesta.context["formulario"].errors
    assert not Movimiento.objects.exists()


def test_concepto_de_otro_hogar_es_rechazado(cliente, catalogo, otro_hogar):
    respuesta = cliente.post(
        URL.format("gasto"), gasto_minimo(concepto_ajeno(otro_hogar)), headers=HTMX
    )

    assert respuesta.status_code == 200
    assert "concepto" in respuesta.context["formulario"].errors
    assert not Movimiento.objects.exists()


def test_campos_sugeridos_al_elegir_concepto(cliente, catalogo):
    respuesta = cliente.get(
        "/movimientos/sugeridos/", {"concepto": catalogo.luz_fidel.pk}, headers=HTMX
    )

    formulario = respuesta.context["formulario"]
    assert formulario["cuenta"].value() == catalogo.nomina.pk
    assert formulario["domicilio"].value() == catalogo.fidel.pk
    assert formulario["metodo_pago"].value() == "tarjeta_debito"


def test_campos_sugeridos_con_concepto_ajeno_o_invalido(cliente, catalogo, otro_hogar):
    ajeno = concepto_ajeno(otro_hogar)

    assert cliente.get("/movimientos/sugeridos/", {"concepto": ajeno.pk}).status_code == 404
    respuesta = cliente.get("/movimientos/sugeridos/", {"concepto": "abc"})
    assert respuesta.status_code == 200
    assert respuesta.context["formulario"]["cuenta"].value() is None


def test_ingreso_de_aguinaldo_extraordinario(cliente, catalogo):
    respuesta = cliente.post(
        URL.format("ingreso"),
        {
            "monto": "20000",
            "tipo_ingreso": "aguinaldo",
            "es_extraordinario": "on",
            "fecha": "2026-12-15",
            "metodo_pago": "transferencia",
            "cuenta": catalogo.nomina.pk,
        },
        headers=HTMX,
    )

    assert respuesta.status_code == 204
    ingreso = Movimiento.objects.get()
    assert ingreso.tipo == Movimiento.Tipo.INGRESO
    assert ingreso.es_extraordinario
    assert ingreso.descripcion == "Aguinaldo"


def test_formulario_de_ingreso_sabe_cuales_son_extraordinarios(cliente, catalogo):
    contenido = cliente.get(URL.format("ingreso"), headers=HTMX).content.decode()

    assert 'data-extraordinarios="aguinaldo ptu bono beca prestamo_recibido"' in contenido


def test_pago_de_deuda_solo_ofrece_tarjetas_y_prestamos(cliente, catalogo):
    respuesta = cliente.get(URL.format("pago_deuda"), headers=HTMX)

    destinos = set(respuesta.context["formulario"].fields["cuenta_destino"].queryset)
    assert destinos == {catalogo.tarjeta, catalogo.prestamo}


def test_pago_de_deuda_reduce_el_saldo(cliente, catalogo):
    cliente.post(
        URL.format("pago_deuda"),
        {
            "monto": "1000",
            "fecha": "2026-10-09",
            "cuenta": catalogo.nomina.pk,
            "cuenta_destino": catalogo.tarjeta.pk,
            "metodo_pago": "transferencia",
        },
        headers=HTMX,
    )

    catalogo.tarjeta.refresh_from_db()
    assert catalogo.tarjeta.saldo_actual == D("5839.01")


def test_tipo_desconocido_da_404(cliente):
    assert cliente.get(URL.format("otro")).status_code == 404


def test_sin_htmx_redirige_tras_guardar(cliente, catalogo):
    respuesta = cliente.post(URL.format("gasto"), gasto_minimo(catalogo.gasolina))

    assert respuesta.status_code == 302


def test_captura_requiere_sesion(client):
    assert client.get(URL.format("gasto")).status_code == 302
