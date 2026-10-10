from decimal import Decimal as D

import pytest

from apps.planeacion.models import SimulacionCredito

pytestmark = pytest.mark.django_db
URL = "/planeacion/simulador/"
EXCEL = {"monto": "30000", "tasa_anual": "25", "meses": "12", "comision_apertura": "1.5"}


def test_simulador_reproduce_el_excel(cliente):
    respuesta = cliente.get(URL, EXCEL)

    contenido = respuesta.content.decode()
    for texto in ("$30,450.00", "1.88%", "$2,857.62", "$3,841.45"):
        assert texto in contenido
    assert len(respuesta.context["amortizacion"].filas) == 12


def test_simulador_sin_datos(cliente):
    respuesta = cliente.get(URL)

    assert respuesta.status_code == 200
    assert respuesta.context["amortizacion"] is None


def test_pagos_anticipados(cliente):
    respuesta = cliente.get(URL, {**EXCEL, "pagos_anticipados": "3=5000\n6: 1,000"})

    filas = respuesta.context["amortizacion"].filas
    assert (filas[2].pago_anticipado, filas[5].pago_anticipado) == (D("5000"), D("1000"))


@pytest.mark.parametrize(
    ("campos", "campo", "texto"),
    [
        ({"pagos_anticipados": "tres mil"}, "pagos_anticipados", "No entiendo"),
        ({"pagos_anticipados": "13=100"}, "__all__", "fuera del plazo"),
        ({"meses": "10000"}, "meses", ""),
        ({"monto": "0"}, "monto", ""),
        ({"tasa_anual": "abc"}, "tasa_anual", ""),
    ],
)
def test_datos_invalidos_muestran_error(cliente, campos, campo, texto):
    respuesta = cliente.get(URL, {**EXCEL, **campos})

    errores = respuesta.context["formulario"].errors
    assert respuesta.status_code == 200
    assert respuesta.context["amortizacion"] is None
    assert campo in errores
    assert texto in str(errores[campo])


def test_guardar_y_abrir_una_simulacion(cliente, hogar):
    respuesta = cliente.post(URL + "guardar/", {**EXCEL, "nombre": "Préstamo personal"})

    simulacion = SimulacionCredito.objects.get()
    assert simulacion.hogar == hogar
    assert (simulacion.tasa_anual, simulacion.comision_apertura) == (D("0.25"), D("0.015"))
    assert respuesta.url == f"{URL}?simulacion={simulacion.pk}"
    contenido = cliente.get(respuesta.url).content.decode()
    assert "$2,857.62" in contenido
    assert "Préstamo personal" in contenido


def test_guardar_con_pagos_anticipados(cliente):
    respuesta = cliente.post(
        URL + "guardar/", {**EXCEL, "nombre": "Con abono", "pagos_anticipados": "3=5000"}
    )

    simulacion = SimulacionCredito.objects.get()
    assert simulacion.pagos_anticipados == {"3": "5000"}
    filas = cliente.get(respuesta.url).context["amortizacion"].filas
    assert filas[2].pago_anticipado == D("5000")


def test_guardar_sin_nombre_no_guarda(cliente):
    respuesta = cliente.post(URL + "guardar/", EXCEL)

    assert respuesta.status_code == 302
    assert not SimulacionCredito.objects.exists()


def test_simulacion_de_otro_hogar_da_404(cliente, otro_hogar):
    ajena = SimulacionCredito.objects.create(
        hogar=otro_hogar, nombre="Ajena", monto=D("1000"), tasa_anual=D("0.1"), meses=12
    )

    assert cliente.get(URL, {"simulacion": ajena.pk}).status_code == 404
    assert cliente.post(f"{URL}{ajena.pk}/eliminar/").status_code == 404
    assert SimulacionCredito.objects.filter(pk=ajena.pk).exists()


def test_eliminar_simulacion(cliente, hogar):
    simulacion = SimulacionCredito.objects.create(
        hogar=hogar, nombre="Vieja", monto=D("1000"), tasa_anual=D("0.1"), meses=12
    )

    assert cliente.post(f"{URL}{simulacion.pk}/eliminar/").status_code == 302
    assert not SimulacionCredito.objects.exists()


def test_mas_enlaza_al_simulador(cliente):
    assert URL in cliente.get("/catalogos/").content.decode()
