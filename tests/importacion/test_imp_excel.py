from decimal import Decimal as D

import pytest

from apps.catalogos.models import Categoria, Concepto, TasaMercado
from apps.catalogos.servicios import sembrar_catalogos
from apps.importacion.excel import ErrorExcel, importar_excel
from apps.presupuesto.models import Periodicidad, PlantillaGasto
from apps.presupuesto.servicios import obtener_plantilla, resumen_plantilla

pytestmark = pytest.mark.django_db


def test_plantilla_reproduce_los_valores_del_excel(excel_ficticio, hogar):
    importar_excel(excel_ficticio(), hogar)

    r = resumen_plantilla(obtener_plantilla(hogar))
    assert r.ingresos_totales == D("32977.52")
    assert r.gastos_totales == D("29235")
    assert r.gastos_fijos == D("26337")
    assert r.presupuesto_hormiga == D("2739")
    assert r.gasto_con_tarjeta == D("1298")
    assert r.meta_ahorro == D("1648.876")


def test_conceptos_en_su_categoria_sin_renglones_vacios(excel_ficticio, hogar):
    resumen = importar_excel(excel_ficticio(), hogar)

    assert resumen.creados["conceptos"] == 28
    assert resumen.creados["gastos de la plantilla"] == 28
    suscripcion = Concepto.objects.get(hogar=hogar, nombre="Suscripciones 1")
    assert suscripcion.categoria.nombre == "Suscripciones"
    assert suscripcion.es_hormiga
    assert not Concepto.objects.filter(hogar=hogar, nombre="-").exists()
    assert resumen.avisos == []


def test_ingresos_y_porcentaje_de_ahorro(excel_ficticio, hogar):
    importar_excel(excel_ficticio(), hogar)

    plantilla = obtener_plantilla(hogar)
    assert plantilla.porcentaje_ahorro == D("0.05")
    salario = plantilla.ingresos.get()  # el bono sin monto no se importa
    assert salario.nombre == "Salario mensual (neto)"
    assert salario.es_fijo
    assert salario.tipo_ingreso == "salario"


def test_concepto_sin_monto_no_entra_a_la_plantilla(excel_ficticio, hogar):
    def con_vuelos(libro):
        libro["Presupuesto"]["I38"] = "Vuelos"
        libro["Presupuesto"]["M38"] = 0

    importar_excel(excel_ficticio(con_vuelos), hogar)

    vuelos = Concepto.objects.get(hogar=hogar, nombre="Vuelos")
    assert vuelos.categoria.nombre == "Viajes"
    assert not PlantillaGasto.objects.filter(concepto=vuelos).exists()


def test_gastos_anuales_quedan_anuales(excel_ficticio, hogar):
    def con_predial(libro):
        libro["Presupuesto"]["O54"] = "Predial"
        libro["Presupuesto"]["S54"] = 1200

    importar_excel(excel_ficticio(con_predial), hogar)

    predial = PlantillaGasto.objects.get(concepto__nombre="Predial")
    assert predial.periodicidad == Periodicidad.ANUAL
    assert predial.monto_mensual() == D("100")


def test_tasas_de_mercado_con_promedio_de_las_repetidas(excel_ficticio, hogar):
    def repetida_y_sin_tasa(libro):
        hoja = libro["No borrar"]
        hoja["F4"], hoja["G4"], hoja["H4"] = "Banco Demo", "Oro", 0.5
        hoja["F5"], hoja["G5"], hoja["H5"] = "Banco Ejemplo", "Básica", "N/D"

    resumen = importar_excel(excel_ficticio(repetida_y_sin_tasa), hogar)

    assert resumen.creados["tasas de mercado"] == 2
    oro = TasaMercado.objects.get(institucion="Banco Demo", producto="Oro")
    assert oro.tasa_promedio == D("0.5952")  # (0.69044 + 0.5) / 2, como AVERAGEIFS
    assert TasaMercado.objects.get(producto="Clásica").tasa_promedio == D("0.7323")
    assert any("Tasas" in aviso for aviso in resumen.avisos)


def test_texto_en_lugar_de_monto(excel_ficticio, hogar):
    def con_texto(libro):
        libro["Presupuesto"]["G22"] = "mil pesos"  # monto de «Casa 1»

    resumen = importar_excel(excel_ficticio(con_texto), hogar)

    assert any("Casa 1" in a and "no es un número" in a for a in resumen.avisos)
    assert Concepto.objects.filter(hogar=hogar, nombre="Casa 1").exists()
    assert not PlantillaGasto.objects.filter(concepto__nombre="Casa 1").exists()


def test_importar_dos_veces_no_duplica(excel_ficticio, hogar):
    ruta = excel_ficticio()
    importar_excel(ruta, hogar)

    segundo = importar_excel(ruta, hogar)

    assert sum(segundo.creados.values()) == 0
    assert segundo.existentes["conceptos"] == 28
    assert PlantillaGasto.objects.filter(plantilla__hogar=hogar).count() == 28


def test_no_modifica_lo_capturado_a_mano(excel_ficticio, hogar):
    sembrar_catalogos(hogar)
    plantilla = obtener_plantilla(hogar)
    plantilla.porcentaje_ahorro = D("0.10")
    plantilla.save()
    casa = Concepto.objects.create(
        hogar=hogar, categoria=Categoria.objects.get(hogar=hogar, nombre="Casa"), nombre="casa 1"
    )
    PlantillaGasto.objects.create(hogar=hogar, plantilla=plantilla, concepto=casa, monto=D("999"))

    importar_excel(excel_ficticio(), hogar)

    plantilla.refresh_from_db()
    assert plantilla.porcentaje_ahorro == D("0.10")
    assert PlantillaGasto.objects.get(concepto=casa).monto == D("999")
    assert Concepto.objects.filter(hogar=hogar, nombre__iexact="casa 1").count() == 1


def test_simulacion_no_guarda_nada(excel_ficticio, hogar):
    resumen = importar_excel(excel_ficticio(), hogar, aplicar=False)

    assert resumen.creados["conceptos"] == 28
    assert not Concepto.objects.filter(hogar=hogar).exists()
    assert not TasaMercado.objects.exists()


def test_archivo_que_no_es_excel(tmp_path, hogar):
    ruta = tmp_path / "planner.xlsx"
    ruta.write_bytes(b"hola")

    with pytest.raises(ErrorExcel, match="No se pudo abrir"):
        importar_excel(ruta, hogar)


def test_hoja_faltante(excel_ficticio, hogar):
    def sin_metas(libro):
        del libro["Metas de Ahorro"]

    with pytest.raises(ErrorExcel, match="Metas de Ahorro"):
        importar_excel(excel_ficticio(sin_metas), hogar)
    assert not Concepto.objects.filter(hogar=hogar).exists()


def test_categorias_en_otro_orden(excel_ficticio, hogar):
    def movida(libro):
        libro["Presupuesto"]["C21"] = "🥑Comida"

    with pytest.raises(ErrorExcel, match="formato esperado"):
        importar_excel(excel_ficticio(movida), hogar)
    assert not Concepto.objects.filter(hogar=hogar).exists()
    assert not TasaMercado.objects.exists()
