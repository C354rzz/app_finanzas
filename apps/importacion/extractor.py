"""Extracción de movimientos con Claude (IMP-05, IMP-10, IMP-11, IMP-13).

Solo recibe texto ya protegido (RNF-03). La respuesta es JSON con un esquema fijo; se valida
con Pydantic y los movimientos que no pasan la validación se descartan y se cuentan.
"""

import json
import os
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Literal

import anthropic
from pydantic import BaseModel, field_validator
from pydantic import ValidationError as ErrorDeValidacion

from apps.calculos.comun import redondear
from apps.importacion.errores import ErrorExtraccion
from apps.movimientos.models import TipoIngreso

MODELO = "claude-opus-5-5"
BETA_RESPALDO = "server-side-fallback-2026-07-01"
MAX_TOKENS = 16000
# Segundos por intento; con 2 reintentos queda por debajo del timeout de la tarea (900 s).
TIEMPO_LIMITE_IA = 240
MONTO_MAXIMO = Decimal("9999999999.99")
# US$ por millón de tokens (entrada, salida) según el modelo que respondió.
PRECIOS_POR_MILLON = {
    "claude-opus-5-5": (Decimal("4"), Decimal("20")),
    "claude-opus-5": (Decimal("5"), Decimal("25")),
    "claude-opus-4-8": (Decimal("5"), Decimal("25")),
}

INSTRUCCIONES = """\
Extraes movimientos de documentos financieros de una familia en México: estados de cuenta \
(débito, tarjetas de crédito y créditos), recibos de nómina y recibos de servicios (luz, agua, \
internet). Recibes el texto del PDF, con algunos datos personales ocultos (por ejemplo [RFC] o \
****1234), y los catálogos del hogar.

Devuelve el tipo de documento, el emisor, el periodo, los últimos 4 dígitos de la cuenta, el saldo \
al corte (solo estados de cuenta) y los movimientos:
- Montos siempre positivos; el tipo da el sentido: gasto (compra, cargo, retiro, comisión), \
ingreso (depósito, abono, nómina, reembolso), pago_deuda (pago a una tarjeta o crédito) o \
transferencia (entre cuentas propias).
- Estado de cuenta: un movimiento por cada operación del periodo, sin omitir ninguno; sin \
saldos, totales ni resúmenes.
- Recibo de nómina: un ingreso con tipo_ingreso «salario» por el neto pagado menos las \
percepciones extraordinarias, con el periodo en la descripción; cada percepción extraordinaria \
(aguinaldo, ptu, bono) es otro ingreso con su tipo_ingreso y es_extraordinario = true.
- Recibo de servicio: no registres movimientos (un recibo no prueba el pago; el cargo llegará en \
el estado de cuenta). Devuelve solo el tipo de documento, el emisor y el periodo.
- categoria, concepto, persona y domicilio: copia exactamente un nombre de los catálogos, o "" si \
ninguno aplica. No inventes nombres.
- confianza: de 0 a 1, qué tan seguro estás de la clasificación del movimiento.
- Fechas en formato AAAA-MM-DD. Usa "" para los datos que no aparezcan.
"""


def _objeto(propiedades):
    return {
        "type": "object",
        "properties": propiedades,
        "required": list(propiedades),
        "additionalProperties": False,
    }


_TEXTO = {"type": "string"}
ESQUEMA = _objeto(
    {
        "tipo_documento": {
            "type": "string",
            "enum": ["estado_cuenta", "nomina", "recibo_servicio", "otro"],
        },
        "emisor": {"type": "string", "description": "Banco o empresa que emite el documento."},
        "periodo_inicio": {"type": "string", "description": "AAAA-MM-DD o vacío."},
        "periodo_fin": {"type": "string", "description": "AAAA-MM-DD o vacío."},
        "ultimos_digitos_cuenta": {"type": "string", "description": "Últimos 4 dígitos o vacío."},
        "saldo_al_corte": {
            "type": "string",
            "description": "Solo estados de cuenta, ej. 6839.01; vacío si no aplica.",
        },
        "movimientos": {
            "type": "array",
            "items": _objeto(
                {
                    "fecha": {"type": "string", "description": "AAAA-MM-DD"},
                    "descripcion": _TEXTO,
                    "monto": {"type": "number", "description": "Siempre positivo."},
                    "tipo": {
                        "type": "string",
                        "enum": ["gasto", "ingreso", "transferencia", "pago_deuda"],
                    },
                    "tipo_ingreso": {"type": "string", "enum": ["", *TipoIngreso.values]},
                    "es_extraordinario": {"type": "boolean"},
                    "categoria": _TEXTO,
                    "concepto": _TEXTO,
                    "persona": _TEXTO,
                    "domicilio": _TEXTO,
                    "confianza": {"type": "number", "description": "De 0 a 1."},
                }
            ),
        },
    }
)


def _decimal(valor):
    try:
        return Decimal(str(valor).replace(",", "").strip())
    except InvalidOperation as error:
        raise ValueError("no es un número") from error


class DocumentoIA(BaseModel):
    tipo_documento: Literal["estado_cuenta", "nomina", "recibo_servicio", "otro"]
    emisor: str
    periodo_inicio: date | None
    periodo_fin: date | None
    ultimos_digitos_cuenta: str
    saldo_al_corte: Decimal | None

    @field_validator("periodo_inicio", "periodo_fin", mode="before")
    @classmethod
    def _fecha_opcional(cls, valor):
        try:
            return date.fromisoformat(str(valor))
        except ValueError:
            return None

    @field_validator("saldo_al_corte", mode="before")
    @classmethod
    def _saldo(cls, valor):
        try:
            saldo = redondear(_decimal(valor))
        except ValueError:
            return None
        return saldo if abs(saldo) <= MONTO_MAXIMO else None

    @field_validator("emisor")
    @classmethod
    def _emisor(cls, valor):
        return valor.strip()[:80]

    @field_validator("ultimos_digitos_cuenta")
    @classmethod
    def _digitos(cls, valor):
        return "".join(caracter for caracter in valor if caracter.isdigit())[-4:]


class MovimientoIA(BaseModel):
    fecha: date
    descripcion: str
    monto: Decimal
    tipo: Literal["gasto", "ingreso", "transferencia", "pago_deuda"]
    tipo_ingreso: str
    es_extraordinario: bool
    categoria: str
    concepto: str
    persona: str
    domicilio: str
    confianza: Decimal

    @field_validator("monto", "confianza", mode="before")
    @classmethod
    def _numero(cls, valor):
        return _decimal(valor)

    @field_validator("monto")
    @classmethod
    def _monto(cls, valor):
        monto = redondear(abs(valor))
        if not Decimal("0.01") <= monto <= MONTO_MAXIMO:
            raise ValueError("monto fuera de rango")
        return monto

    @field_validator("confianza")
    @classmethod
    def _confianza(cls, valor):
        return redondear(min(max(valor, Decimal("0")), Decimal("1")))

    @field_validator("descripcion")
    @classmethod
    def _descripcion(cls, valor):
        texto = " ".join(valor.split())[:255]
        if not texto:
            raise ValueError("sin descripción")
        return texto

    @field_validator("tipo_ingreso")
    @classmethod
    def _tipo_ingreso(cls, valor):
        return valor if valor in TipoIngreso.values else ""


@dataclass(frozen=True)
class Uso:
    modelo: str
    tokens_entrada: int
    tokens_salida: int
    costo_usd: Decimal


@dataclass(frozen=True)
class ResultadoExtraccion:
    documento: DocumentoIA
    movimientos: list
    descartados: int
    uso: Uso


def construir_mensaje(texto, catalogos):
    return (
        "Catálogos del hogar (usa estos nombres tal cual):\n<catalogos>\n"
        + json.dumps(catalogos, ensure_ascii=False, indent=1)
        + "\n</catalogos>\n\nTexto del documento:\n<documento>\n"
        + texto
        + "\n</documento>"
    )


def costo_usd(modelo, entrada, salida):
    por_entrada, por_salida = PRECIOS_POR_MILLON.get(modelo, PRECIOS_POR_MILLON[MODELO])
    return redondear((entrada * por_entrada + salida * por_salida) / Decimal(1_000_000), 4)


def uso_de(respuesta):
    uso = respuesta.usage
    entrada = (
        uso.input_tokens
        + (getattr(uso, "cache_creation_input_tokens", None) or 0)
        + (getattr(uso, "cache_read_input_tokens", None) or 0)
    )
    salida = uso.output_tokens
    return Uso(
        modelo=respuesta.model,
        tokens_entrada=entrada,
        tokens_salida=salida,
        costo_usd=costo_usd(respuesta.model, entrada, salida),
    )


def interpretar(texto_json, uso):
    try:
        datos = json.loads(texto_json)
    except json.JSONDecodeError as error:
        raise ErrorExtraccion("La IA devolvió una respuesta que no se pudo leer.") from error
    if not isinstance(datos, dict):
        raise ErrorExtraccion("La IA devolvió una respuesta que no se pudo leer.")
    crudos = datos.pop("movimientos", None) or []
    try:
        documento = DocumentoIA.model_validate(datos)
    except ErrorDeValidacion as error:
        raise ErrorExtraccion("La IA devolvió datos del documento incompletos.") from error
    movimientos, descartados = [], 0
    for crudo in crudos if isinstance(crudos, list) else []:
        try:
            movimientos.append(MovimientoIA.model_validate(crudo))
        except ErrorDeValidacion:
            descartados += 1
    return ResultadoExtraccion(documento, movimientos, descartados, uso)


class ExtractorClaude:
    """Envía el texto protegido a Claude y devuelve los datos estructurados."""

    def __init__(self, cliente=None):
        self._cliente = cliente

    @property
    def cliente(self):
        if self._cliente is None:
            if not (os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")):
                raise ErrorExtraccion(
                    "Falta configurar la clave de la API de Claude (ANTHROPIC_API_KEY) en el "
                    "archivo .env."
                )
            self._cliente = anthropic.Anthropic(timeout=TIEMPO_LIMITE_IA, max_retries=2)
        return self._cliente

    def extraer(self, texto, catalogos):
        respuesta = self.cliente.beta.messages.create(
            model=MODELO,
            max_tokens=MAX_TOKENS,
            betas=[BETA_RESPALDO],
            fallbacks="default",
            output_config={"effort": "low", "format": {"type": "json_schema", "schema": ESQUEMA}},
            system=INSTRUCCIONES,
            messages=[{"role": "user", "content": construir_mensaje(texto, catalogos)}],
        )
        if respuesta.stop_reason == "refusal":
            raise ErrorExtraccion("La IA no aceptó procesar este documento.")
        if respuesta.stop_reason == "max_tokens":
            raise ErrorExtraccion(
                "El documento es demasiado largo para procesarlo de una sola vez."
            )
        texto_json = next((b.text for b in respuesta.content if b.type == "text"), "")
        if not texto_json:
            raise ErrorExtraccion("La IA no devolvió datos.")
        return interpretar(texto_json, uso_de(respuesta))
