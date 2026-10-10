from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

from apps.calculos.credito import amortizar
from apps.calculos.metas import aporte_mensual_meta
from apps.catalogos.models import DINERO, TASA, Cuenta, Domicilio
from apps.core.models import ModeloDeHogar

MESES_MAXIMOS = 600
NO_NEGATIVO = [MinValueValidator(Decimal("0"))]
POSITIVO = [MinValueValidator(Decimal("0.01"))]
PLAZO = [MinValueValidator(1), MaxValueValidator(MESES_MAXIMOS)]


class MetaAhorro(ModeloDeHogar):
    class Tipo(models.TextChoices):
        AUTO = "auto", "🚗 Auto"
        CASA = "casa", "🏡 Casa"
        COMPRA_IMPORTANTE = "compra_importante", "🛍️ Compra importante"
        EDUCACION = "educacion", "🎓 Educación"
        FONDO_EMERGENCIA = "fondo_emergencia", "🛟 Fondo de emergencia"
        REGALO = "regalo", "🎁 Regalo"
        REMODELACION = "remodelacion", "🔨 Remodelación"
        VACACIONES = "vacaciones", "🏖️ Vacaciones"
        OTRO = "otro", "🎲 Otro"

    tipo = models.CharField(max_length=20, choices=Tipo.choices, default=Tipo.OTRO)
    nombre = models.CharField(max_length=80)
    monto_objetivo = models.DecimalField("meta de ahorro total", validators=POSITIVO, **DINERO)
    ahorro_actual = models.DecimalField(
        "ahorro actual", default=Decimal("0"), validators=NO_NEGATIVO, **DINERO
    )
    meses = models.PositiveSmallIntegerField("meses para ahorrar", default=12, validators=PLAZO)
    tasa_anual = models.DecimalField(
        "tasa de interés anual", default=Decimal("0.10"), validators=NO_NEGATIVO, **TASA
    )
    fecha_inicio = models.DateField("fecha de inicio", default=timezone.localdate)
    cuenta = models.ForeignKey(
        Cuenta,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        help_text="Opcional: la cuenta donde guardas este ahorro.",
    )
    activa = models.BooleanField(default=True)

    class Meta:
        verbose_name = "meta de ahorro"
        verbose_name_plural = "metas de ahorro"
        ordering = ["-activa", "nombre"]

    def __str__(self):
        return self.nombre

    def aporte_mensual(self):
        """RN-05: ahorro mensual necesario para llegar a la meta."""
        return aporte_mensual_meta(
            self.monto_objetivo, self.ahorro_actual, self.meses, self.tasa_anual
        )


class Activo(ModeloDeHogar):
    class Tipo(models.TextChoices):
        ACCIONES = "acciones", "📈 Acciones"
        AUTO = "auto", "🚗 Auto"
        INMUEBLE = "inmueble", "🏡 Casa o departamento"
        CUENTA_AHORRO = "cuenta_ahorro", "💰 Cuenta de ahorro"
        CUENTA_INVERSION = "cuenta_inversion", "📊 Cuenta de inversión"
        AFORE = "afore", "👵 Afore"
        STOCK_OPTIONS = "stock_options", "🧾 Stock options"
        TERRENO = "terreno", "🌄 Terreno"
        OTRO = "otro", "🎲 Otro"

    tipo = models.CharField(max_length=20, choices=Tipo.choices, default=Tipo.OTRO)
    nombre = models.CharField(max_length=120)
    valor_actual = models.DecimalField(
        "valor actual", max_digits=14, decimal_places=2, validators=NO_NEGATIVO
    )
    fecha_valuacion = models.DateField("fecha de valuación", default=timezone.localdate)
    domicilio = models.ForeignKey(
        Domicilio,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        help_text="Opcional: si el activo es un inmueble.",
    )
    cuenta = models.ForeignKey(
        Cuenta,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        help_text="Opcional: si el valor viene de una cuenta (ahorro, inversión, afore).",
    )
    activo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "activo"
        verbose_name_plural = "activos"
        ordering = ["-activo", "-valor_actual", "nombre"]

    def __str__(self):
        return self.nombre


class SimulacionCredito(ModeloDeHogar):
    nombre = models.CharField(max_length=80)
    monto = models.DecimalField("crédito total", validators=POSITIVO, **DINERO)
    tasa_anual = models.DecimalField("tasa de interés anual", validators=NO_NEGATIVO, **TASA)
    meses = models.PositiveSmallIntegerField("duración en meses", validators=PLAZO)
    comision_apertura = models.DecimalField(
        "comisión por apertura", default=Decimal("0"), validators=NO_NEGATIVO, **TASA
    )
    pagos_anticipados = models.JSONField(
        "pagos anticipados", default=dict, blank=True, help_text='{"<mes>": "<monto>"}'
    )

    class Meta:
        verbose_name = "simulación de crédito"
        verbose_name_plural = "simulaciones de crédito"
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre

    def anticipados(self):
        return {int(mes): Decimal(str(monto)) for mes, monto in self.pagos_anticipados.items()}

    def amortizacion(self):
        """RN-07: tabla de amortización con comisión y pagos anticipados."""
        return amortizar(
            self.monto, self.tasa_anual, self.meses, self.comision_apertura, self.anticipados()
        )

    def clean(self):
        super().clean()
        if None in (self.monto, self.tasa_anual, self.meses, self.comision_apertura):
            return
        if not 1 <= self.meses <= MESES_MAXIMOS:
            return
        try:
            self.amortizacion()
        except (ValueError, TypeError, InvalidOperation) as error:
            raise ValidationError(str(error)) from error
