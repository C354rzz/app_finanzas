"""Servicios de importación: registro, procesamiento (worker) y revisión de propuestas."""

import logging
from dataclasses import dataclass

import anthropic
from django.conf import settings
from django.core.files.base import ContentFile
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone
from django.utils.module_loading import import_string
from django_q.tasks import async_task

from apps.calculos.comun import CERO
from apps.catalogos.models import Categoria, Concepto, Cuenta, Domicilio, Persona
from apps.importacion import archivos
from apps.importacion.clasificacion import (
    aplicar_regla,
    buscar_duplicado,
    buscar_regla,
    normalizar,
)
from apps.importacion.errores import ErrorImportacion
from apps.importacion.models import Documento, MovimientoPropuesto
from apps.importacion.texto import extraer_texto, proteger_datos
from apps.movimientos.models import TIPOS_DEUDA, MetodoPago, Movimiento, TipoIngreso
from apps.movimientos.servicios import metodo_para_cuenta

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Rechazo:
    nombre: str
    motivo: str


def registrar_archivos(hogar, usuario, subidos, cuenta=None):
    """IMP-01/02: guarda cada PDF (o los PDFs de un ZIP) y lo encola."""
    documentos, rechazos = [], []
    for subido in subidos:
        if subido.size > archivos.TAMANO_MAXIMO:
            rechazos.append(Rechazo(subido.name, f"pesa más de {archivos.megas()} MB"))
            continue
        try:
            pdfs = archivos.pdfs_del_archivo(subido.name, subido.read())
        except ErrorImportacion as error:
            rechazos.append(Rechazo(subido.name, str(error)))
            continue
        for nombre, contenido in pdfs:
            huella = archivos.huella(contenido)
            previo = Documento.objects.del_hogar(hogar).filter(sha256=huella).first()
            if previo:
                fecha = timezone.localtime(previo.creado_en)
                rechazos.append(Rechazo(nombre, f"ya se importó el {fecha:%d/%m/%Y}"))
                continue
            documentos.append(_registrar_pdf(hogar, usuario, nombre, contenido, huella, cuenta))
    return documentos, rechazos


def _registrar_pdf(hogar, usuario, nombre, contenido, huella, cuenta):
    documento = Documento(
        hogar=hogar, nombre_original=nombre[:255], sha256=huella, cuenta=cuenta, subido_por=usuario
    )
    documento.archivo.save(f"{huella}.pdf", ContentFile(contenido), save=False)
    documento.save()
    encolar_procesamiento(documento)
    return documento


def encolar_procesamiento(documento):
    async_task("apps.importacion.tareas.procesar", documento.pk)


def costo_del_mes(hogar, hoy=None):
    """IMP-13: costo de IA acumulado en el mes (US$)."""
    hoy = hoy or timezone.localdate()
    total = (
        Documento.objects.del_hogar(hogar)
        .filter(creado_en__year=hoy.year, creado_en__month=hoy.month)
        .aggregate(total=Sum("costo_estimado_usd"))["total"]
    )
    return total or CERO


def reintentar(documento):
    documento.estado = Documento.Estado.SUBIDO
    documento.error = ""
    documento.save(update_fields=["estado", "error", "actualizado_en"])
    encolar_procesamiento(documento)


def eliminar_documento(documento):
    """Borra el PDF y el documento; los movimientos ya aceptados se conservan."""
    documento.archivo.delete(save=False)
    documento.delete()


def obtener_extractor():
    return import_string(settings.IMPORTACION_EXTRACTOR)()


@dataclass
class Catalogo:
    """Catálogos activos del hogar, buscables por nombre normalizado."""

    categorias: dict
    conceptos: dict
    personas: dict
    domicilios: dict
    cuentas: list

    @classmethod
    def del_hogar(cls, hogar):
        def activos(modelo):
            return modelo.objects.del_hogar(hogar).filter(activo=True)

        conceptos = activos(Concepto).select_related("categoria", "domicilio")
        return cls(
            categorias={normalizar(c.nombre): c for c in activos(Categoria)},
            conceptos={normalizar(str(c)): c for c in conceptos},
            personas={normalizar(p.nombre): p for p in activos(Persona)},
            domicilios={normalizar(d.alias): d for d in activos(Domicilio)},
            cuentas=list(activos(Cuenta)),
        )

    def buscar(self, tipo, nombre):
        return getattr(self, tipo).get(normalizar(nombre)) if nombre else None

    def cuenta_por_digitos(self, digitos):
        coincidencias = [c for c in self.cuentas if digitos and c.ultimos_digitos == digitos]
        return coincidencias[0] if len(coincidencias) == 1 else None

    def para_ia(self):
        return {
            "categorias": [c.nombre for c in self.categorias.values()],
            "conceptos": [
                {"concepto": str(c), "categoria": c.categoria.nombre}
                for c in self.conceptos.values()
            ],
            "personas": [p.nombre for p in self.personas.values()],
            "domicilios": [
                {"alias": d.alias, "direccion": d.direccion} for d in self.domicilios.values()
            ],
            "cuentas": [
                {
                    "nombre": c.nombre,
                    "tipo": c.get_tipo_display(),
                    "ultimos_digitos": c.ultimos_digitos,
                }
                for c in self.cuentas
            ],
        }


def procesar_documento(documento_id):
    """Texto → datos protegidos → IA → reglas y duplicados → propuestas por revisar."""
    documento = Documento.objects.select_related("hogar", "cuenta").filter(pk=documento_id).first()
    if documento is None or documento.estado not in (
        Documento.Estado.SUBIDO,
        Documento.Estado.ERROR,
    ):
        return
    documento.estado = Documento.Estado.PROCESANDO
    documento.save(update_fields=["estado", "actualizado_en"])
    try:
        with documento.archivo.open("rb") as archivo:
            texto, documento.paginas = extraer_texto(archivo.read())
        catalogo = Catalogo.del_hogar(documento.hogar)
        resultado = obtener_extractor().extraer(proteger_datos(texto), catalogo.para_ia())
        _guardar_resultado(documento, catalogo, resultado)
    except ErrorImportacion as error:
        _marcar_error(documento, str(error))
    except anthropic.AuthenticationError:
        _marcar_error(
            documento,
            "Falta configurar la clave de la API de Claude (ANTHROPIC_API_KEY) en el archivo .env.",
        )
    except anthropic.APIError as error:
        _marcar_error(
            documento,
            f"No se pudo contactar a la IA ({type(error).__name__}). Intenta de nuevo más tarde.",
        )
    except Exception:
        logger.exception("Error al procesar el documento %s", documento_id)
        _marcar_error(documento, "Ocurrió un error inesperado al procesar el documento.")


def _marcar_error(documento, mensaje):
    documento.estado = Documento.Estado.ERROR
    documento.error = mensaje
    documento.save(update_fields=["estado", "error", "paginas", "actualizado_en"])


@transaction.atomic
def _guardar_resultado(documento, catalogo, resultado):
    datos = resultado.documento
    documento.tipo = datos.tipo_documento
    documento.emisor = datos.emisor
    documento.periodo_inicio = datos.periodo_inicio
    documento.periodo_fin = datos.periodo_fin
    documento.saldo_al_corte = datos.saldo_al_corte
    if documento.cuenta is None:
        documento.cuenta = catalogo.cuenta_por_digitos(datos.ultimos_digitos_cuenta)
    uso = resultado.uso
    documento.modelo_ia = uso.modelo
    documento.tokens_entrada = uso.tokens_entrada
    documento.tokens_salida = uso.tokens_salida
    documento.costo_estimado_usd = uso.costo_usd
    documento.aviso = (
        f"{resultado.descartados} movimiento(s) no se pudieron leer; revisa el PDF original."
        if resultado.descartados
        else ""
    )
    documento.error = ""
    documento.propuestas.all().delete()
    for movimiento in resultado.movimientos:
        _crear_propuesta(documento, catalogo, movimiento)
    documento.estado = Documento.Estado.POR_REVISAR
    documento.save()


def _crear_propuesta(documento, catalogo, datos):
    tipo = datos.tipo
    cuenta, cuenta_destino = documento.cuenta, None
    if tipo == Movimiento.Tipo.PAGO_DEUDA and cuenta is not None and cuenta.tipo in TIPOS_DEUDA:
        cuenta, cuenta_destino = None, documento.cuenta
    tipo_ingreso = ""
    if tipo == Movimiento.Tipo.INGRESO:
        por_defecto = (
            TipoIngreso.SALARIO if documento.tipo == Documento.Tipo.NOMINA else TipoIngreso.OTRO
        )
        tipo_ingreso = datos.tipo_ingreso or por_defecto
    concepto = categoria = None
    if tipo == Movimiento.Tipo.GASTO:
        concepto = catalogo.buscar("conceptos", datos.concepto)
        categoria = (
            concepto.categoria if concepto else catalogo.buscar("categorias", datos.categoria)
        )
    propuesta = MovimientoPropuesto(
        hogar=documento.hogar,
        documento=documento,
        fecha=datos.fecha,
        descripcion_original=datos.descripcion,
        descripcion=datos.descripcion,
        monto=datos.monto,
        tipo=tipo,
        tipo_ingreso=tipo_ingreso,
        es_extraordinario=tipo == Movimiento.Tipo.INGRESO and datos.es_extraordinario,
        metodo_pago=_metodo(tipo, cuenta),
        categoria=categoria,
        concepto=concepto,
        persona=catalogo.buscar("personas", datos.persona),
        domicilio=catalogo.buscar("domicilios", datos.domicilio),
        cuenta=cuenta,
        cuenta_destino=cuenta_destino,
        confianza=datos.confianza,
    )
    regla = buscar_regla(documento.hogar, documento.emisor, datos.descripcion)
    if regla is not None:
        aplicar_regla(propuesta, regla)
    propuesta.posible_duplicado_de = buscar_duplicado(
        documento.hogar, datos.fecha, datos.monto, cuenta or cuenta_destino
    )
    propuesta.save()


def _metodo(tipo, cuenta):
    if tipo != Movimiento.Tipo.GASTO:
        return MetodoPago.TRANSFERENCIA
    return metodo_para_cuenta(cuenta)
