import json
from datetime import date
from decimal import Decimal as D

import anthropic
import httpx2
import pytest
from django.core.files.base import ContentFile

from apps.importacion import servicios, tareas
from apps.importacion.archivos import huella
from apps.importacion.errores import ErrorExtraccion
from apps.importacion.extractor import Uso, interpretar
from apps.importacion.models import Documento, MovimientoPropuesto, ReglaClasificacion
from apps.movimientos.models import MetodoPago, Movimiento
from apps.movimientos.servicios import guardar_movimiento

pytestmark = pytest.mark.django_db
USO = Uso("claude-opus-5-5", 10000, 2000, D("0.0800"))
TEXTO = "BANCO DEMO estado de cuenta\nRFC XAXX010101000\nCompra OXXO 85.50"


def movimiento_ia(**campos):
    datos = {
        "fecha": "2026-09-10",
        "descripcion": "OXXO SUC 1234",
        "monto": 85.5,
        "tipo": "gasto",
        "tipo_ingreso": "",
        "es_extraordinario": False,
        "categoria": "Comida",
        "concepto": "",
        "persona": "",
        "domicilio": "",
        "confianza": 0.9,
    }
    datos.update(campos)
    return datos


def resultado(movimientos, **documento):
    datos = {
        "tipo_documento": "estado_cuenta",
        "emisor": "Banco Demo",
        "periodo_inicio": "2026-09-06",
        "periodo_fin": "2026-10-05",
        "ultimos_digitos_cuenta": "",
        "saldo_al_corte": "6839.01",
        **documento,
        "movimientos": movimientos,
    }
    return interpretar(json.dumps(datos), USO)


class ExtractorFalso:
    def __init__(self, respuesta):
        self.respuesta = respuesta
        self.llamadas = []

    def extraer(self, texto, catalogos):
        self.llamadas.append((texto, catalogos))
        if isinstance(self.respuesta, Exception):
            raise self.respuesta
        return self.respuesta


@pytest.fixture
def usar_extractor(monkeypatch):
    def usar(respuesta):
        falso = ExtractorFalso(respuesta)
        monkeypatch.setattr(servicios, "obtener_extractor", lambda: falso)
        return falso

    return usar


@pytest.fixture
def documento_pdf(hogar, crear_pdf):
    def crear(*paginas, cuenta=None):
        datos = crear_pdf(*paginas)
        documento = Documento(
            hogar=hogar, nombre_original="estado.pdf", sha256=huella(datos), cuenta=cuenta
        )
        documento.archivo.save("x.pdf", ContentFile(datos), save=False)
        documento.save()
        return documento

    return crear


def procesar(documento):
    servicios.procesar_documento(documento.pk)
    documento.refresh_from_db()
    return documento


def test_procesa_y_crea_propuestas(catalogo, documento_pdf, usar_extractor):
    usar_extractor(
        resultado(
            [
                movimiento_ia(concepto="gasolina", persona="MONZE", monto=650),
                movimiento_ia(descripcion="INVENTADO", categoria="Inexistente"),
            ]
        )
    )

    documento = procesar(documento_pdf(TEXTO, cuenta=catalogo.nomina))

    assert documento.estado == Documento.Estado.POR_REVISAR
    assert (documento.tipo, documento.emisor, documento.paginas) == (
        "estado_cuenta",
        "Banco Demo",
        1,
    )
    assert (documento.periodo_fin, documento.saldo_al_corte) == (date(2026, 10, 5), D("6839.01"))
    assert (documento.modelo_ia, documento.tokens_entrada, documento.tokens_salida) == (
        "claude-opus-5-5",
        10000,
        2000,
    )
    assert documento.costo_estimado_usd == D("0.0800")
    gasolina, inventado = documento.propuestas.all()
    assert (gasolina.concepto, gasolina.categoria) == (
        catalogo.gasolina,
        catalogo.categorias["Transporte"],
    )
    assert (gasolina.persona, gasolina.cuenta, gasolina.monto) == (
        catalogo.monze,
        catalogo.nomina,
        D("650.00"),
    )
    assert gasolina.metodo_pago == MetodoPago.TARJETA_DEBITO
    assert gasolina.estado == MovimientoPropuesto.Estado.PENDIENTE
    assert (inventado.categoria, inventado.concepto) == (None, None)


def test_a_la_ia_solo_va_texto_protegido_y_catalogos(catalogo, documento_pdf, usar_extractor):
    extractor = usar_extractor(resultado([]))

    procesar(documento_pdf(TEXTO))

    ((texto, catalogos),) = extractor.llamadas
    assert "XAXX010101000" not in texto
    assert "[RFC]" in texto
    assert "Compra OXXO 85.50" in texto
    assert "estado.pdf" not in texto
    assert "Gasolina" in [c["concepto"] for c in catalogos["conceptos"]]
    assert {"alias": "Casa Fidel", "direccion": ""} in catalogos["domicilios"]


def test_la_regla_del_hogar_manda_sobre_la_ia(catalogo, documento_pdf, usar_extractor):
    casa = catalogo.categorias["Casa"]
    regla = ReglaClasificacion.objects.create(
        hogar=catalogo.gasolina.hogar, patron="oxxo", categoria=casa, persona=catalogo.monze
    )
    usar_extractor(resultado([movimiento_ia(categoria="Comida")]))

    propuesta = procesar(documento_pdf(TEXTO)).propuestas.get()

    assert (propuesta.categoria, propuesta.persona, propuesta.regla) == (
        casa,
        catalogo.monze,
        regla,
    )
    assert propuesta.confianza == D("1")


def test_marca_posible_duplicado(catalogo, documento_pdf, usar_extractor):
    existente = guardar_movimiento(
        Movimiento(
            hogar=catalogo.nomina.hogar,
            tipo=Movimiento.Tipo.GASTO,
            monto=D("85.50"),
            concepto=catalogo.gasolina,
            cuenta=catalogo.nomina,
            fecha=date(2026, 9, 11),
        )
    )
    usar_extractor(resultado([movimiento_ia()]))

    propuesta = procesar(documento_pdf(TEXTO, cuenta=catalogo.nomina)).propuestas.get()

    assert propuesta.posible_duplicado_de == existente


def test_pago_a_la_tarjeta_en_su_estado_de_cuenta(catalogo, documento_pdf, usar_extractor):
    usar_extractor(
        resultado([movimiento_ia(tipo="pago_deuda", descripcion="PAGO RECIBIDO", monto=2000)])
    )

    propuesta = procesar(documento_pdf(TEXTO, cuenta=catalogo.tarjeta)).propuestas.get()

    assert (propuesta.cuenta, propuesta.cuenta_destino) == (None, catalogo.tarjeta)
    assert (propuesta.metodo_pago, propuesta.categoria) == (MetodoPago.TRANSFERENCIA, None)


def test_cuenta_por_ultimos_digitos(catalogo, documento_pdf, usar_extractor):
    catalogo.nomina.ultimos_digitos = "1234"
    catalogo.nomina.save()
    usar_extractor(resultado([movimiento_ia()], ultimos_digitos_cuenta="****1234"))

    documento = procesar(documento_pdf(TEXTO))

    assert documento.cuenta == catalogo.nomina
    assert documento.propuestas.get().cuenta == catalogo.nomina


def test_nomina(catalogo, documento_pdf, usar_extractor):
    usar_extractor(
        resultado(
            [
                movimiento_ia(tipo="ingreso", descripcion="NETO QUINCENA", monto=8000),
                movimiento_ia(
                    tipo="ingreso", tipo_ingreso="aguinaldo", es_extraordinario=True, monto=20000
                ),
            ],
            tipo_documento="nomina",
        )
    )

    salario, aguinaldo = procesar(documento_pdf(TEXTO)).propuestas.all()

    assert (salario.tipo_ingreso, salario.es_extraordinario, salario.categoria) == (
        "salario",
        False,
        None,
    )
    assert (aguinaldo.tipo_ingreso, aguinaldo.es_extraordinario) == ("aguinaldo", True)


def test_aviso_si_hubo_movimientos_ilegibles(catalogo, documento_pdf, usar_extractor):
    usar_extractor(resultado([movimiento_ia(), movimiento_ia(monto=0)]))

    documento = procesar(documento_pdf(TEXTO))

    assert "1 movimiento(s) no se pudieron leer" in documento.aviso
    assert documento.propuestas.count() == 1


def test_pdf_sin_texto_queda_en_error(documento_pdf, usar_extractor):
    extractor = usar_extractor(resultado([]))

    documento = procesar(documento_pdf("", ""))

    assert documento.estado == Documento.Estado.ERROR
    assert "OCR" in documento.error
    assert extractor.llamadas == []


def test_error_de_la_ia_queda_en_el_documento(documento_pdf, usar_extractor):
    usar_extractor(ErrorExtraccion("La IA no aceptó procesar este documento."))

    documento = procesar(documento_pdf(TEXTO))

    assert (documento.estado, documento.error) == (
        Documento.Estado.ERROR,
        "La IA no aceptó procesar este documento.",
    )


def test_sin_conexion_con_la_ia(documento_pdf, usar_extractor):
    peticion = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
    usar_extractor(anthropic.APIConnectionError(request=peticion))

    documento = procesar(documento_pdf(TEXTO))

    assert documento.estado == Documento.Estado.ERROR
    assert "No se pudo contactar a la IA" in documento.error


def test_error_inesperado_no_deja_el_documento_atascado(documento_pdf, usar_extractor):
    usar_extractor(RuntimeError("falla interna"))

    documento = procesar(documento_pdf(TEXTO))

    assert documento.estado == Documento.Estado.ERROR
    assert "error inesperado" in documento.error


def test_reprocesar_reemplaza_las_propuestas(catalogo, documento_pdf, usar_extractor):
    usar_extractor(resultado([movimiento_ia(), movimiento_ia(descripcion="OTRO")]))
    documento = procesar(documento_pdf(TEXTO))
    Documento.objects.filter(pk=documento.pk).update(estado=Documento.Estado.ERROR)

    documento = procesar(documento)

    assert documento.propuestas.count() == 2


def test_documento_ya_procesado_no_se_vuelve_a_procesar(catalogo, documento_pdf, usar_extractor):
    extractor = usar_extractor(resultado([movimiento_ia()]))
    documento = procesar(documento_pdf(TEXTO))

    procesar(documento)

    assert len(extractor.llamadas) == 1
    assert documento.propuestas.count() == 1


def test_tarea_del_worker(catalogo, documento_pdf, usar_extractor):
    usar_extractor(resultado([movimiento_ia()]))
    documento = documento_pdf(TEXTO)

    tareas.procesar(documento.pk)

    documento.refresh_from_db()
    assert documento.estado == Documento.Estado.POR_REVISAR
