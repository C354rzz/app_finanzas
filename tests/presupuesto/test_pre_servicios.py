from decimal import Decimal as D

import pytest
from django.core.exceptions import ValidationError

from apps.calculos.comun import redondear
from apps.catalogos.models import Categoria, Concepto
from apps.presupuesto.mensajes import (
    ALERTA,
    BIEN,
    CUIDADO,
    mensaje_ahorro,
    mensaje_disponible,
    mensaje_recorte,
)
from apps.presupuesto.models import (
    Periodicidad,
    PlantillaGasto,
    PlantillaIngreso,
    PresupuestoMes,
    PresupuestoMesGasto,
)
from apps.presupuesto.servicios import (
    gastos_del_mes,
    obtener_plantilla,
    obtener_presupuesto_mes,
    resincronizar_mes,
    resumen_mes,
    resumen_plantilla,
)

pytestmark = pytest.mark.django_db


def test_una_plantilla_por_hogar(hogar):
    plantilla = obtener_plantilla(hogar)

    assert obtener_plantilla(hogar) == plantilla
    assert plantilla.porcentaje_ahorro == D("0.05")


def test_resumen_de_la_plantilla_reproduce_el_excel(plantilla_excel):
    r = resumen_plantilla(plantilla_excel)

    assert r.ingresos_totales == D("32977.52")
    assert r.gastos_totales == D("29235")
    assert r.gastos_fijos == D("26337")
    assert r.gastos_variables == D("2898")
    assert r.disponible == D("3742.52")
    assert r.meta_ahorro == D("1648.876")
    assert r.presupuesto_hormiga == D("2739")
    assert redondear(r.maximo_diario_hormiga) == D("91.30")
    assert r.recorte_necesario is None
    assert r.gasto_con_tarjeta == D("1298")


def test_el_mes_se_crea_copiando_la_plantilla(plantilla_excel, hogar):
    octubre = obtener_presupuesto_mes(hogar, 2026, 10)

    assert octubre.gastos.count() == 28
    assert octubre.ingresos.count() == 1
    assert octubre.porcentaje_ahorro == D("0.05")
    assert resumen_mes(octubre) == resumen_plantilla(plantilla_excel)


def test_consultar_de_nuevo_no_duplica_ni_pisa_ajustes(plantilla_excel, hogar):
    octubre = obtener_presupuesto_mes(hogar, 2026, 10)
    renglon = octubre.gastos.first()
    renglon.monto_mensual = D("1")
    renglon.save()

    otra_vez = obtener_presupuesto_mes(hogar, 2026, 10)

    assert otra_vez.pk == octubre.pk
    assert otra_vez.gastos.count() == 28
    renglon.refresh_from_db()
    assert renglon.monto_mensual == D("1")


def test_ajustar_un_mes_no_afecta_la_plantilla_ni_otros_meses(plantilla_excel, hogar):
    obtener_presupuesto_mes(hogar, 2026, 10).gastos.update(monto_mensual=D("0"))

    noviembre = obtener_presupuesto_mes(hogar, 2026, 11)

    assert resumen_mes(noviembre).gastos_totales == D("29235")
    assert resumen_plantilla(plantilla_excel).gastos_totales == D("29235")


def test_cambios_en_la_plantilla_solo_aplican_a_meses_nuevos(plantilla_excel, hogar):
    octubre = obtener_presupuesto_mes(hogar, 2026, 10)

    plantilla_excel.gastos.update(monto=D("0"))

    assert resumen_mes(octubre).gastos_totales == D("29235")
    assert resumen_mes(obtener_presupuesto_mes(hogar, 2026, 11)).gastos_totales == D("0")


def test_resincronizar_reemplaza_el_mes(plantilla_excel, hogar):
    octubre = obtener_presupuesto_mes(hogar, 2026, 10)
    octubre.gastos.all().delete()
    octubre.porcentaje_ahorro = D("0.20")
    octubre.save()

    resincronizar_mes(octubre)

    octubre.refresh_from_db()
    assert octubre.gastos.count() == 28
    assert octubre.porcentaje_ahorro == D("0.05")


def test_gasto_anual_se_prorratea_en_el_mes(hogar, catalogo):
    plantilla = obtener_plantilla(hogar)
    seguro = Concepto.objects.create(
        hogar=hogar, categoria=catalogo.categorias["Gastos anuales"], nombre="Seguro del auto"
    )
    PlantillaGasto.objects.create(
        hogar=hogar,
        plantilla=plantilla,
        concepto=seguro,
        monto=D("1000"),
        periodicidad=Periodicidad.ANUAL,
    )

    octubre = obtener_presupuesto_mes(hogar, 2026, 10)

    assert octubre.gastos.get().monto_mensual == D("83.33")
    assert resumen_plantilla(plantilla).gastos_totales == D("1000") / 12


def test_mes_invalido(hogar):
    with pytest.raises(ValueError):
        obtener_presupuesto_mes(hogar, 2026, 13)


def test_concepto_de_otro_hogar_en_la_plantilla_es_invalido(hogar, otro_hogar):
    ajena = Categoria.objects.create(hogar=otro_hogar, nombre="Casa")
    concepto_ajeno = Concepto.objects.create(hogar=otro_hogar, categoria=ajena, nombre="Luz")
    renglon = PlantillaGasto(
        hogar=hogar, plantilla=obtener_plantilla(hogar), concepto=concepto_ajeno, monto=D("1")
    )

    with pytest.raises(ValidationError) as error:
        renglon.full_clean()

    assert "concepto" in error.value.message_dict


def test_filtros_por_domicilio_y_persona(hogar, catalogo):
    plantilla = obtener_plantilla(hogar)
    catalogo.gasolina.persona = catalogo.monze
    catalogo.gasolina.save()
    for concepto, monto in [(catalogo.luz_fidel, "500"), (catalogo.gasolina, "1400")]:
        PlantillaGasto.objects.create(
            hogar=hogar, plantilla=plantilla, concepto=concepto, monto=D(monto)
        )
    PlantillaIngreso.objects.create(
        hogar=hogar, plantilla=plantilla, nombre="Salario", monto=D("20000")
    )
    PlantillaIngreso.objects.create(
        hogar=hogar,
        plantilla=plantilla,
        nombre="Beca",
        tipo_ingreso="beca",
        monto=D("1000"),
        persona=catalogo.monze,
    )
    octubre = obtener_presupuesto_mes(hogar, 2026, 10)

    en_fidel = resumen_mes(octubre, domicilio=catalogo.fidel)
    de_monze = resumen_mes(octubre, persona=catalogo.monze)

    assert (en_fidel.gastos_totales, en_fidel.ingresos_totales) == (D("500"), D("0"))
    assert (de_monze.gastos_totales, de_monze.ingresos_totales) == (D("1400"), D("1000"))
    conceptos = [g.concepto for g in gastos_del_mes(octubre, domicilio=catalogo.fidel)]
    assert conceptos == [catalogo.luz_fidel]


def test_mensajes_del_porcentaje_de_ahorro():
    assert mensaje_ahorro(D("0")).startswith("Podrías ahorrar más")
    assert mensaje_ahorro(D("0.05")).startswith("Podrías ahorrar más")
    assert mensaje_ahorro(D("0.12")).startswith("Este es un buen porcentaje")
    assert mensaje_ahorro(D("0.15")).startswith("¡Buena meta de ahorro!")
    assert mensaje_ahorro(D("0.20")).startswith("¡Muy bien")
    assert mensaje_ahorro(D("0.50")).startswith("¡Genial!")


def test_mensaje_del_disponible():
    assert mensaje_disponible(D("3742.52"), D("1648.876"))[0] == BIEN
    assert mensaje_disponible(D("1000"), D("1648.876"))[0] == CUIDADO
    assert mensaje_disponible(D("-5"), D("10"))[0] == ALERTA
    assert mensaje_disponible(D("0"), D("0"))[0] == BIEN


def test_mensaje_del_recorte():
    assert mensaje_recorte(None).startswith("👏¡Bien!")
    assert mensaje_recorte(D("10")).startswith("⚠️Considera recortar")


def test_borrar_el_hogar_borra_su_presupuesto(plantilla_excel, hogar):
    obtener_presupuesto_mes(hogar, 2026, 10)

    hogar.delete()

    assert not PresupuestoMes.objects.exists()
    assert not PresupuestoMesGasto.objects.exists()
