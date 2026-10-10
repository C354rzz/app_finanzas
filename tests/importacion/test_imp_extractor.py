import json
from datetime import date
from decimal import Decimal as D
from types import SimpleNamespace

import pytest

from apps.importacion.errores import ErrorExtraccion
from apps.importacion.extractor import (
    ESQUEMA,
    ExtractorClaude,
    construir_mensaje,
)

MOVIMIENTO = {
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


def movimiento(**campos):
    return {**MOVIMIENTO, **campos}


RESPUESTA = {
    "tipo_documento": "estado_cuenta",
    "emisor": "Banco Demo",
    "periodo_inicio": "2026-09-06",
    "periodo_fin": "2026-10-05",
    "ultimos_digitos_cuenta": "****1234",
    "saldo_al_corte": "6,839.01",
    "movimientos": [
        MOVIMIENTO,
        movimiento(fecha="2026-09-15", descripcion="DEPOSITO NOMINA", monto=15000,
                   tipo="ingreso", tipo_ingreso="salario", categoria="", confianza=0.95),
        movimiento(fecha="2026-09-20", descripcion="PAGO TARJETA", monto=-2000,
                   tipo="pago_deuda", categoria="", confianza=1.5),
        movimiento(descripcion="CARGO EN CERO", monto=0),
        movimiento(descripcion="FECHA MAL", fecha="21/09/2026"),
        movimiento(descripcion="TIPO RARO", tipo="regalo"),
        movimiento(descripcion="ENORME", monto=1e12),
    ],
}  # fmt: skip


class ClienteFalso:
    def __init__(self, respuesta):
        self.respuesta = respuesta
        self.llamadas = []
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self._crear))

    def _crear(self, **kwargs):
        self.llamadas.append(kwargs)
        return self.respuesta


def respuesta(datos=RESPUESTA, stop_reason="end_turn", modelo="claude-opus-5-5", texto=None):
    contenido = [
        SimpleNamespace(type="text", text=texto if texto is not None else json.dumps(datos))
    ]
    return SimpleNamespace(
        content=contenido,
        stop_reason=stop_reason,
        model=modelo,
        usage=SimpleNamespace(
            input_tokens=10000,
            output_tokens=2000,
            cache_creation_input_tokens=None,
            cache_read_input_tokens=None,
        ),
    )


def extraer(cliente):
    return ExtractorClaude(cliente).extraer("texto del estado", {"categorias": ["Comida"]})


def objetos(esquema):
    if esquema.get("type") == "object":
        yield esquema
        for propiedad in esquema["properties"].values():
            yield from objetos(propiedad)
    elif esquema.get("type") == "array":
        yield from objetos(esquema["items"])


def test_esquema_estricto():
    for objeto in objetos(ESQUEMA):
        assert objeto["additionalProperties"] is False
        assert set(objeto["required"]) == set(objeto["properties"])


def test_peticion_a_claude():
    cliente = ClienteFalso(respuesta())

    extraer(cliente)

    (llamada,) = cliente.llamadas
    assert llamada["model"] == "claude-opus-5-5"
    assert llamada["betas"] == ["server-side-fallback-2026-07-01"]
    assert llamada["fallbacks"] == "default"
    assert llamada["output_config"]["effort"] == "low"
    assert llamada["output_config"]["format"] == {"type": "json_schema", "schema": ESQUEMA}
    assert "thinking" not in llamada
    (mensaje,) = llamada["messages"]
    assert mensaje["role"] == "user"
    assert isinstance(mensaje["content"], str)
    assert "texto del estado" in mensaje["content"]


def test_interpreta_la_respuesta():
    resultado = extraer(ClienteFalso(respuesta()))

    documento = resultado.documento
    assert (documento.tipo_documento, documento.emisor) == ("estado_cuenta", "Banco Demo")
    assert (documento.periodo_inicio, documento.periodo_fin) == (
        date(2026, 9, 6),
        date(2026, 10, 5),
    )
    assert (documento.ultimos_digitos_cuenta, documento.saldo_al_corte) == ("1234", D("6839.01"))
    assert [m.monto for m in resultado.movimientos] == [D("85.50"), D("15000.00"), D("2000.00")]
    assert resultado.movimientos[1].tipo_ingreso == "salario"
    assert resultado.movimientos[2].confianza == D("1.00")
    assert resultado.descartados == 4


def test_uso_y_costo():
    uso = extraer(ClienteFalso(respuesta())).uso

    assert (uso.modelo, uso.tokens_entrada, uso.tokens_salida) == ("claude-opus-5-5", 10000, 2000)
    assert uso.costo_usd == D("0.0800")


def test_costo_si_respondio_el_modelo_de_respaldo():
    uso = extraer(ClienteFalso(respuesta(modelo="claude-opus-4-8"))).uso

    assert uso.costo_usd == D("0.1000")


@pytest.mark.parametrize(
    ("falsa", "mensaje"),
    [
        (respuesta(stop_reason="refusal"), "no aceptó"),
        (respuesta(stop_reason="max_tokens"), "demasiado largo"),
        (respuesta(texto="esto no es json"), "no se pudo leer"),
        (respuesta(texto=""), "no devolvió datos"),
        (respuesta({**RESPUESTA, "tipo_documento": "factura"}), "incompletos"),
    ],
)
def test_respuestas_problematicas(falsa, mensaje):
    with pytest.raises(ErrorExtraccion, match=mensaje):
        extraer(ClienteFalso(falsa))


def test_datos_opcionales_vacios_o_mal_escritos():
    datos = {**RESPUESTA, "periodo_inicio": "", "periodo_fin": "5 de octubre",
             "saldo_al_corte": "", "ultimos_digitos_cuenta": "", "movimientos": []}  # fmt: skip

    documento = extraer(ClienteFalso(respuesta(datos))).documento

    assert (documento.periodo_inicio, documento.periodo_fin, documento.saldo_al_corte) == (
        None,
        None,
        None,
    )
    assert documento.ultimos_digitos_cuenta == ""


def test_descripcion_larga_se_recorta():
    datos = {**RESPUESTA, "movimientos": [movimiento(descripcion="X " * 300)]}

    (unico,) = extraer(ClienteFalso(respuesta(datos))).movimientos

    assert len(unico.descripcion) == 255


def test_mensaje_con_catalogos_y_texto():
    mensaje = construir_mensaje("Compra OXXO 85.50", {"categorias": ["Comida", "Café"]})

    assert "<documento>\nCompra OXXO 85.50\n</documento>" in mensaje
    assert "Café" in mensaje


def test_el_cliente_real_se_crea_hasta_usarlo():
    assert ExtractorClaude()._cliente is None


def test_sin_clave_de_api(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN", raising=False)

    with pytest.raises(ErrorExtraccion, match="ANTHROPIC_API_KEY"):
        ExtractorClaude().extraer("texto", {})
