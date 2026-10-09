from datetime import date
from decimal import Decimal as D

import pytest
from django.utils import timezone

from apps.catalogos.models import Categoria
from apps.movimientos.models import MetodoPago, Movimiento, TipoIngreso
from apps.movimientos.servicios import guardar_movimiento

pytestmark = pytest.mark.django_db
HTMX = {"HX-Request": "true"}


def registrar(hogar, **campos):
    campos.setdefault("fecha", date(2026, 10, 5))
    campos["monto"] = D(campos["monto"])
    return guardar_movimiento(Movimiento(hogar=hogar, **campos))


def gasto(catalogo, monto="650", **campos):
    campos.setdefault("concepto", catalogo.gasolina)
    return registrar(catalogo.gasolina.hogar, tipo=Movimiento.Tipo.GASTO, monto=monto, **campos)


def pago(catalogo, monto="1000"):
    return registrar(
        catalogo.tarjeta.hogar,
        tipo=Movimiento.Tipo.PAGO_DEUDA,
        monto=monto,
        cuenta=catalogo.nomina,
        cuenta_destino=catalogo.tarjeta,
        metodo_pago=MetodoPago.TRANSFERENCIA,
    )


def test_lista_del_mes_con_totales(cliente, catalogo):
    gasto(catalogo)
    registrar(
        catalogo.nomina.hogar,
        tipo=Movimiento.Tipo.INGRESO,
        tipo_ingreso=TipoIngreso.SALARIO,
        monto="15000",
        fecha=date(2026, 10, 15),
    )
    gasto(catalogo, "999", fecha=date(2026, 9, 30))

    respuesta = cliente.get("/movimientos/2026/10/")

    contenido = respuesta.content.decode()
    assert "Octubre 2026" in contenido
    assert "$650.00" in contenido
    assert "$15,000.00" in contenido
    assert "$999.00" not in contenido
    assert respuesta.context["totales"].gastos == D("650")


def test_lista_aplica_los_filtros(cliente, catalogo):
    de_monze = gasto(catalogo, "10", persona=catalogo.monze)
    gasto(catalogo, "20")

    respuesta = cliente.get("/movimientos/2026/10/", {"persona": catalogo.monze.pk})

    assert list(respuesta.context["movimientos"]) == [de_monze]


def test_movimientos_redirige_al_mes_actual(cliente):
    hoy = timezone.localdate()

    respuesta = cliente.get("/movimientos/")

    assert respuesta.url == f"/movimientos/{hoy.year}/{hoy.month}/"


def test_mes_invalido_da_404(cliente):
    assert cliente.get("/movimientos/2026/13/").status_code == 404


def test_navegacion_de_diciembre_a_enero(cliente):
    contenido = cliente.get("/movimientos/2026/12/").content.decode()

    assert "/movimientos/2027/1/" in contenido
    assert "/movimientos/2026/11/" in contenido


def test_formulario_de_edicion_muestra_los_datos(cliente, catalogo):
    movimiento = gasto(catalogo)

    respuesta = cliente.get(f"/movimientos/{movimiento.pk}/editar/", headers=HTMX)

    assert respuesta.status_code == 200
    assert 'value="650.00"' in respuesta.content.decode()


def test_editar_un_gasto(cliente, catalogo):
    movimiento = gasto(catalogo)

    respuesta = cliente.post(
        f"/movimientos/{movimiento.pk}/editar/",
        {
            "monto": "700",
            "concepto": catalogo.gasolina.pk,
            "fecha": "2026-10-05",
            "metodo_pago": "efectivo",
        },
        headers=HTMX,
    )

    assert respuesta.status_code == 204
    movimiento.refresh_from_db()
    assert movimiento.monto == D("700")


def test_editar_un_pago_de_deuda_ajusta_el_saldo(cliente, catalogo):
    movimiento = pago(catalogo)

    cliente.post(
        f"/movimientos/{movimiento.pk}/editar/",
        {
            "monto": "1200",
            "fecha": "2026-10-05",
            "cuenta": catalogo.nomina.pk,
            "cuenta_destino": catalogo.tarjeta.pk,
            "metodo_pago": "transferencia",
        },
        headers=HTMX,
    )

    catalogo.tarjeta.refresh_from_db()
    assert catalogo.tarjeta.saldo_actual == D("5639.01")


def test_eliminar_un_pago_de_deuda_devuelve_el_saldo(cliente, catalogo):
    movimiento = pago(catalogo)

    respuesta = cliente.post(f"/movimientos/{movimiento.pk}/eliminar/", headers=HTMX)

    assert respuesta.status_code == 204
    catalogo.tarjeta.refresh_from_db()
    assert catalogo.tarjeta.saldo_actual == D("6839.01")
    assert not Movimiento.objects.exists()


def test_eliminar_requiere_post(cliente, catalogo):
    movimiento = gasto(catalogo)

    assert cliente.get(f"/movimientos/{movimiento.pk}/eliminar/").status_code == 405


def test_movimiento_de_otro_hogar_da_404(cliente, otro_hogar):
    ajena = Categoria.objects.create(hogar=otro_hogar, nombre="Casa")
    ajeno = registrar(otro_hogar, tipo=Movimiento.Tipo.GASTO, monto="10", categoria=ajena)

    assert cliente.get(f"/movimientos/{ajeno.pk}/editar/").status_code == 404
    assert cliente.post(f"/movimientos/{ajeno.pk}/eliminar/").status_code == 404
    assert Movimiento.objects.filter(pk=ajeno.pk).exists()


def test_exportar_csv_del_mes(cliente, catalogo):
    gasto(catalogo)

    respuesta = cliente.get("/movimientos/2026/10/csv/")

    assert respuesta["Content-Type"].startswith("text/csv")
    assert "movimientos-2026-10.csv" in respuesta["Content-Disposition"]
    lineas = respuesta.content.decode("utf-8-sig").splitlines()
    assert lineas[0].startswith("fecha,tipo,descripción")
    assert "Gasolina" in lineas[1]
    assert "650.00" in lineas[1]


def test_exportar_csv_del_anio(cliente, catalogo):
    gasto(catalogo, fecha=date(2026, 3, 1))
    gasto(catalogo, fecha=date(2026, 10, 1))
    gasto(catalogo, fecha=date(2025, 12, 31))

    respuesta = cliente.get("/movimientos/2026/csv/")

    assert len(respuesta.content.decode("utf-8-sig").splitlines()) == 3
