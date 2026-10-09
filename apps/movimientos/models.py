from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

from apps.catalogos.models import DINERO, Categoria, Concepto, Cuenta, Domicilio, Persona
from apps.core.fechas import ANIO_MAXIMO, ANIO_MINIMO
from apps.core.models import ModeloDeHogar


class TipoIngreso(models.TextChoices):
    SALARIO = "salario", "Salario"
    AGUINALDO = "aguinaldo", "Aguinaldo"
    PTU = "ptu", "Utilidades (PTU)"
    BONO = "bono", "Bono"
    BECA = "beca", "Beca"
    PRESTAMO_RECIBIDO = "prestamo_recibido", "Préstamo recibido"
    REEMBOLSO = "reembolso", "Reembolso"
    VENTA = "venta", "Venta"
    OTRO = "otro", "Otro"


class MetodoPago(models.TextChoices):
    EFECTIVO = "efectivo", "Efectivo"
    TRANSFERENCIA = "transferencia", "Transferencia"
    TARJETA_DEBITO = "tarjeta_debito", "Tarjeta de débito"
    TARJETA_CREDITO = "tarjeta_credito", "Tarjeta de crédito"
    DOMICILIACION = "domiciliacion", "Domiciliación"


# RF-MOV-02: tipos de ingreso marcados como extraordinarios por defecto (RN-13).
INGRESOS_EXTRAORDINARIOS = (
    TipoIngreso.AGUINALDO,
    TipoIngreso.PTU,
    TipoIngreso.BONO,
    TipoIngreso.BECA,
    TipoIngreso.PRESTAMO_RECIBIDO,
)
TIPOS_DEUDA = (Cuenta.Tipo.CREDITO, Cuenta.Tipo.PRESTAMO)


def es_extraordinario_por_defecto(tipo_ingreso):
    return tipo_ingreso in INGRESOS_EXTRAORDINARIOS


class Movimiento(ModeloDeHogar):
    class Tipo(models.TextChoices):
        GASTO = "gasto", "Gasto"
        INGRESO = "ingreso", "Ingreso"
        TRANSFERENCIA = "transferencia", "Transferencia"
        PAGO_DEUDA = "pago_deuda", "Pago de deuda"

    class Origen(models.TextChoices):
        MANUAL = "manual", "Manual"
        IMPORTADO = "importado", "Importado"

    fecha = models.DateField(default=timezone.localdate)
    tipo = models.CharField(max_length=15, choices=Tipo.choices)
    monto = models.DecimalField(validators=[MinValueValidator(Decimal("0.01"))], **DINERO)
    descripcion = models.CharField("descripción", max_length=255, blank=True)
    categoria = models.ForeignKey(
        Categoria, null=True, blank=True, on_delete=models.RESTRICT, verbose_name="categoría"
    )
    concepto = models.ForeignKey(Concepto, null=True, blank=True, on_delete=models.RESTRICT)
    tipo_ingreso = models.CharField(
        "tipo de ingreso", max_length=20, choices=TipoIngreso.choices, blank=True
    )
    es_extraordinario = models.BooleanField("extraordinario", default=False)
    metodo_pago = models.CharField(
        "método de pago", max_length=15, choices=MetodoPago.choices, default=MetodoPago.EFECTIVO
    )
    cuenta = models.ForeignKey(
        Cuenta, null=True, blank=True, on_delete=models.RESTRICT, related_name="movimientos"
    )
    cuenta_destino = models.ForeignKey(
        Cuenta,
        null=True,
        blank=True,
        on_delete=models.RESTRICT,
        related_name="movimientos_entrantes",
        verbose_name="cuenta destino",
    )
    persona = models.ForeignKey(
        Persona, null=True, blank=True, on_delete=models.RESTRICT, related_name="movimientos"
    )
    domicilio = models.ForeignKey(
        Domicilio, null=True, blank=True, on_delete=models.RESTRICT, related_name="movimientos"
    )
    es_hormiga = models.BooleanField("hormiga 🐜", default=False)
    notas = models.TextField(blank=True)
    origen = models.CharField(max_length=10, choices=Origen.choices, default=Origen.MANUAL)
    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )

    class Meta:
        ordering = ["-fecha", "-id"]
        indexes = [
            models.Index(fields=["hogar", "fecha"], name="mov_hogar_fecha"),
            models.Index(fields=["hogar", "categoria", "fecha"], name="mov_hogar_categoria_fecha"),
            models.Index(fields=["hogar", "cuenta", "fecha"], name="mov_hogar_cuenta_fecha"),
            models.Index(fields=["hogar", "persona"], name="mov_hogar_persona"),
            models.Index(fields=["hogar", "domicilio"], name="mov_hogar_domicilio"),
        ]

    def __str__(self):
        return f"{self.fecha:%d/%m/%Y} {self.descripcion} {self.monto}"

    def clean(self):
        if self.concepto_id and not self.categoria_id:
            self.categoria = self.concepto.categoria
        super().clean()
        errores = {}
        tipo = self.Tipo
        if self.fecha and not ANIO_MINIMO <= self.fecha.year <= ANIO_MAXIMO:
            errores["fecha"] = f"La fecha debe estar entre {ANIO_MINIMO} y {ANIO_MAXIMO}."
        if self.tipo == tipo.GASTO and not self.categoria_id:
            errores["categoria"] = "Indica la categoría del gasto."
        if (
            self.concepto_id
            and self.categoria_id
            and self.concepto.categoria_id != self.categoria_id
        ):
            errores["concepto"] = "El concepto no pertenece a la categoría elegida."
        if self.tipo == tipo.INGRESO and not self.tipo_ingreso:
            errores["tipo_ingreso"] = "Indica el tipo de ingreso."
        if self.tipo != tipo.INGRESO and (self.tipo_ingreso or self.es_extraordinario):
            errores["tipo_ingreso"] = "Solo los ingresos llevan tipo de ingreso."
        if self.tipo in (tipo.TRANSFERENCIA, tipo.PAGO_DEUDA):
            errores.update(self._errores_de_cuentas())
        elif self.cuenta_destino_id:
            errores["cuenta_destino"] = (
                "Solo las transferencias y los pagos de deuda llevan cuenta destino."
            )
        if errores:
            raise ValidationError(errores)

    def _errores_de_cuentas(self):
        if not self.cuenta_id:
            return {"cuenta": "Indica la cuenta de origen."}
        if not self.cuenta_destino_id:
            return {"cuenta_destino": "Indica la cuenta destino."}
        if self.cuenta_destino_id == self.cuenta_id:
            return {"cuenta_destino": "La cuenta destino debe ser distinta de la de origen."}
        if self.tipo == self.Tipo.PAGO_DEUDA and self.cuenta_destino.tipo not in TIPOS_DEUDA:
            return {
                "cuenta_destino": "El pago de deuda debe ir a una tarjeta de crédito o un préstamo."
            }
        return {}

    def save(self, *args, **kwargs):
        if not self.descripcion:
            self.descripcion = self.descripcion_sugerida()
        super().save(*args, **kwargs)

    def descripcion_sugerida(self):
        if self.concepto_id:
            return self.concepto.nombre
        if self.tipo_ingreso:
            return self.get_tipo_ingreso_display()
        if self.categoria_id:
            return self.categoria.nombre
        return self.get_tipo_display()
