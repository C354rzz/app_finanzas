from decimal import Decimal

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from apps.calculos.presupuesto import ANUAL, MENSUAL, LineaGasto
from apps.catalogos.models import DINERO, Concepto, Persona
from apps.core.models import ModeloDeHogar
from apps.movimientos.models import TipoIngreso

NO_NEGATIVO = [MinValueValidator(Decimal("0"))]
PORCENTAJE = {
    "max_digits": 5,
    "decimal_places": 4,
    "validators": [MinValueValidator(Decimal("0")), MaxValueValidator(Decimal("1"))],
}


class Periodicidad(models.TextChoices):
    MENSUAL = MENSUAL, "Mensual"
    ANUAL = ANUAL, "Anual"


class RenglonIngreso(ModeloDeHogar):
    nombre = models.CharField(max_length=80)
    tipo_ingreso = models.CharField(
        "tipo de ingreso", max_length=20, choices=TipoIngreso.choices, default=TipoIngreso.SALARIO
    )
    es_fijo = models.BooleanField("fijo", default=True)
    monto = models.DecimalField(validators=NO_NEGATIVO, **DINERO)
    persona = models.ForeignKey(
        Persona, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )

    class Meta:
        abstract = True
        ordering = ["-monto", "nombre"]

    def __str__(self):
        return self.nombre


class RenglonGasto(ModeloDeHogar):
    concepto = models.ForeignKey(Concepto, on_delete=models.RESTRICT, related_name="+")
    es_fijo = models.BooleanField("fijo", default=False)
    con_tarjeta = models.BooleanField("con tarjeta", default=False)
    es_hormiga = models.BooleanField("hormiga 🐜", default=False)

    class Meta:
        abstract = True
        ordering = ["concepto__categoria__orden", "concepto__nombre"]

    def __str__(self):
        return str(self.concepto)


class PlantillaPresupuesto(ModeloDeHogar):
    porcentaje_ahorro = models.DecimalField("% de ahorro", default=Decimal("0.05"), **PORCENTAJE)

    class Meta:
        verbose_name = "plantilla de presupuesto"
        verbose_name_plural = "plantillas de presupuesto"
        constraints = [models.UniqueConstraint(fields=["hogar"], name="plantilla_unica_por_hogar")]

    def __str__(self):
        return f"Plantilla de {self.hogar}"


class PlantillaIngreso(RenglonIngreso):
    plantilla = models.ForeignKey(
        PlantillaPresupuesto, on_delete=models.CASCADE, related_name="ingresos"
    )

    class Meta(RenglonIngreso.Meta):
        verbose_name = "ingreso de la plantilla"
        verbose_name_plural = "ingresos de la plantilla"


class PlantillaGasto(RenglonGasto):
    plantilla = models.ForeignKey(
        PlantillaPresupuesto, on_delete=models.CASCADE, related_name="gastos"
    )
    monto = models.DecimalField(validators=NO_NEGATIVO, **DINERO)
    periodicidad = models.CharField(
        max_length=7, choices=Periodicidad.choices, default=Periodicidad.MENSUAL
    )

    class Meta(RenglonGasto.Meta):
        verbose_name = "gasto de la plantilla"
        verbose_name_plural = "gastos de la plantilla"
        constraints = [
            models.UniqueConstraint(fields=["plantilla", "concepto"], name="plantilla_gasto_unico")
        ]

    def monto_mensual(self):
        """RN-03: anual → monto / 12."""
        return LineaGasto(monto=self.monto, periodicidad=self.periodicidad).monto_mensual()


class PresupuestoMes(ModeloDeHogar):
    anio = models.PositiveSmallIntegerField("año")
    mes = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(12)])
    porcentaje_ahorro = models.DecimalField("% de ahorro", **PORCENTAJE)
    cerrado = models.BooleanField(default=False)

    class Meta:
        verbose_name = "presupuesto del mes"
        verbose_name_plural = "presupuestos del mes"
        ordering = ["-anio", "-mes"]
        constraints = [
            models.UniqueConstraint(fields=["hogar", "anio", "mes"], name="presupuesto_mes_unico")
        ]

    def __str__(self):
        return f"Presupuesto {self.mes:02d}/{self.anio}"


class PresupuestoMesIngreso(RenglonIngreso):
    presupuesto = models.ForeignKey(
        PresupuestoMes, on_delete=models.CASCADE, related_name="ingresos"
    )

    class Meta(RenglonIngreso.Meta):
        verbose_name = "ingreso del mes"
        verbose_name_plural = "ingresos del mes"


class PresupuestoMesGasto(RenglonGasto):
    presupuesto = models.ForeignKey(PresupuestoMes, on_delete=models.CASCADE, related_name="gastos")
    monto_mensual = models.DecimalField("monto mensual", validators=NO_NEGATIVO, **DINERO)

    class Meta(RenglonGasto.Meta):
        verbose_name = "gasto del mes"
        verbose_name_plural = "gastos del mes"
        constraints = [
            models.UniqueConstraint(
                fields=["presupuesto", "concepto"], name="presupuesto_mes_gasto_unico"
            )
        ]
