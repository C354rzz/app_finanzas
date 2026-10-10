import re
from decimal import Decimal as D

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.catalogos.models import Concepto, Cuenta
from apps.catalogos.servicios import tasa_sugerida
from apps.importacion.excel import importar_excel
from apps.planeacion.models import Activo, MetaAhorro

pytestmark = pytest.mark.django_db


def test_tarjetas_con_tasa_capturada_o_de_mercado(excel_ficticio, hogar):
    importar_excel(excel_ficticio(), hogar)

    oro = Cuenta.objects.get(hogar=hogar, nombre="Banco Demo Oro")
    assert oro.tipo == Cuenta.Tipo.CREDITO
    assert (oro.institucion, oro.producto) == ("Banco Demo", "Oro")
    assert oro.saldo_actual == D("6839.01")
    assert oro.linea_credito == D("7100")
    assert oro.tasa_anual == D("0.45")
    assert oro.paga_total_mensual is False
    clasica = Cuenta.objects.get(hogar=hogar, nombre="Banco Demo Clásica")
    assert clasica.tasa_anual is None  # en el Excel era el promedio de mercado (fórmula)
    assert tasa_sugerida(clasica) == D("0.7323")
    assert clasica.paga_total_mensual is True
    assert not Cuenta.objects.filter(hogar=hogar, institucion="Otro").exists()


def test_creditos(excel_ficticio, hogar):
    resumen = importar_excel(excel_ficticio(), hogar)

    auto = Cuenta.objects.get(hogar=hogar, nombre="Préstamo auto")
    assert auto.tipo == Cuenta.Tipo.PRESTAMO
    assert auto.monto_inicial == D("41130")
    assert auto.saldo_actual == D("38679.72")
    assert auto.mensualidad == D("1500")
    assert resumen.creados["créditos"] == 1
    assert resumen.creados["tarjetas"] == 2


def test_metas_con_monto(excel_ficticio, hogar):
    importar_excel(excel_ficticio(), hogar)

    regalo = MetaAhorro.objects.get(hogar=hogar, nombre="Regalo")
    assert regalo.tipo == MetaAhorro.Tipo.REGALO
    assert regalo.monto_objetivo == D("3000")
    assert regalo.ahorro_actual == D("0")
    assert regalo.meses == 6
    assert regalo.tasa_anual == D("0.1000")
    vacaciones = MetaAhorro.objects.get(hogar=hogar, nombre="Vacaciones")
    assert vacaciones.tipo == MetaAhorro.Tipo.VACACIONES
    assert vacaciones.ahorro_actual == D("2000")
    assert MetaAhorro.objects.filter(hogar=hogar).count() == 2


def test_meta_con_meses_invalidos_usa_12_y_avisa(excel_ficticio, hogar):
    def meses_raros(libro):
        libro["Metas de Ahorro"]["E12"] = "medio año"

    resumen = importar_excel(excel_ficticio(meses_raros), hogar)

    assert MetaAhorro.objects.get(hogar=hogar, nombre="Regalo").meses == 12
    assert any("Regalo" in aviso for aviso in resumen.avisos)


def test_activos(excel_ficticio, hogar):
    importar_excel(excel_ficticio(), hogar)

    casa = Activo.objects.get(hogar=hogar, nombre="Casa ejemplo")
    assert casa.tipo == Activo.Tipo.INMUEBLE
    assert casa.valor_actual == D("1500000")
    ahorro = Activo.objects.get(hogar=hogar, nombre="Cuentas de Ahorro")
    assert ahorro.tipo == Activo.Tipo.CUENTA_AHORRO
    assert Activo.objects.filter(hogar=hogar).count() == 3


def test_segunda_importacion_no_duplica_ni_sobrescribe(excel_ficticio, hogar):
    ruta = excel_ficticio()
    importar_excel(ruta, hogar)
    Cuenta.objects.filter(hogar=hogar, nombre="Banco Demo Oro").update(saldo_actual=D("1"))

    segundo = importar_excel(ruta, hogar)

    assert sum(segundo.creados.values()) == 0
    assert segundo.existentes["tarjetas"] == 2
    assert segundo.existentes["metas"] == 2
    assert segundo.existentes["activos"] == 3
    assert Cuenta.objects.get(hogar=hogar, nombre="Banco Demo Oro").saldo_actual == D("1")


def test_comando_simula_por_omision(excel_ficticio, hogar, capsys):
    call_command("importar_excel", str(excel_ficticio()))

    salida = capsys.readouterr().out
    assert "Simulación" in salida
    assert re.search(r"^conceptos\s+28\s+0$", salida, re.MULTILINE)
    assert "Avisos: 0" in salida
    assert not Concepto.objects.filter(hogar=hogar).exists()


def test_comando_aplicar(excel_ficticio, hogar, usuario):
    call_command("importar_excel", str(excel_ficticio()), email=usuario.email, aplicar=True)

    assert Concepto.objects.filter(hogar=hogar).count() == 28
    assert Activo.objects.filter(hogar=hogar).count() == 3


def test_comando_no_muestra_nombres_sin_detalle(excel_ficticio, hogar, capsys):
    def con_texto(libro):
        libro["Presupuesto"]["G22"] = "mil pesos"

    ruta = str(excel_ficticio(con_texto))
    call_command("importar_excel", ruta)
    sin_detalle = capsys.readouterr().out
    call_command("importar_excel", ruta, detalle=True)
    con_detalle = capsys.readouterr().out

    assert "Avisos: 1 (usa --detalle para verlos)" in sin_detalle
    assert "Casa 1" not in sin_detalle
    assert "Casa 1" in con_detalle


def test_comando_con_email_sin_hogar(excel_ficticio, hogar):
    with pytest.raises(CommandError, match="No hay un hogar"):
        call_command("importar_excel", str(excel_ficticio()), email="nadie@example.com")


def test_comando_con_archivo_invalido(tmp_path, hogar):
    ruta = tmp_path / "planner.xlsx"
    ruta.write_bytes(b"hola")

    with pytest.raises(CommandError, match="No se pudo abrir"):
        call_command("importar_excel", str(ruta))


def test_renglones_repetidos_en_el_mismo_excel_no_se_pierden(excel_ficticio, hogar):
    def repetidos(libro):
        libro["Patrimonio"]["C8"], libro["Patrimonio"]["E8"] = "💰Cuentas de Ahorro", "-"
        libro["Patrimonio"]["G8"] = 9000
        deudas = libro["Deudas"]
        deudas["C6"], deudas["D6"], deudas["F6"], deudas["G6"] = "Banco Demo", "Oro", 500, 1000

    resumen = importar_excel(excel_ficticio(repetidos), hogar)

    assert Activo.objects.get(hogar=hogar, nombre="Cuentas de Ahorro (2)").valor_actual == D("9000")
    assert Cuenta.objects.get(hogar=hogar, nombre="Banco Demo Oro (2)").saldo_actual == D("500")
    assert resumen.existentes["activos"] == 0
    assert resumen.existentes["tarjetas"] == 0
    assert sum("repetido" in aviso for aviso in resumen.avisos) == 2
