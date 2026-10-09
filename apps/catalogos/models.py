from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from apps.core.models import ConMarcasDeTiempo, ModeloDeHogar

DINERO = {"max_digits": 12, "decimal_places": 2}
TASA = {"max_digits": 7, "decimal_places": 4}
DIA_DEL_MES = [MinValueValidator(1), MaxValueValidator(31)]
AYUDA_SUGERIDO = "Opcional. Se precarga al registrar un movimiento y puedes cambiarlo en cada uno."


class Persona(ModeloDeHogar):
    nombre = models.CharField(max_length=80)
    parentesco = models.CharField(max_length=40, blank=True)
    activo = models.BooleanField(default=True)

    class Meta:
        ordering = ["nombre"]
        constraints = [
            models.UniqueConstraint(fields=["hogar", "nombre"], name="persona_nombre_unico")
        ]

    def __str__(self):
        return self.nombre


class Domicilio(ModeloDeHogar):
    alias = models.CharField(max_length=80)
    direccion = models.CharField(max_length=255, blank=True)
    activo = models.BooleanField(default=True)

    class Meta:
        ordering = ["alias"]
        constraints = [
            models.UniqueConstraint(fields=["hogar", "alias"], name="domicilio_alias_unico")
        ]

    def __str__(self):
        return self.alias


class Categoria(ModeloDeHogar):
    nombre = models.CharField(max_length=60)
    icono = models.CharField(max_length=8, blank=True)
    orden = models.PositiveSmallIntegerField(default=0)
    activo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "categoría"
        ordering = ["orden", "nombre"]
        constraints = [
            models.UniqueConstraint(fields=["hogar", "nombre"], name="categoria_nombre_unico")
        ]

    def __str__(self):
        return f"{self.icono} {self.nombre}".strip()


class Cuenta(ModeloDeHogar):
    class Tipo(models.TextChoices):
        EFECTIVO = "efectivo", "Efectivo"
        DEBITO = "debito", "Débito"
        CREDITO = "credito", "Tarjeta de crédito"
        PRESTAMO = "prestamo", "Préstamo / crédito"
        AHORRO = "ahorro", "Ahorro"
        INVERSION = "inversion", "Inversión"

    nombre = models.CharField(max_length=80)
    tipo = models.CharField(max_length=10, choices=Tipo.choices)
    institucion = models.CharField(max_length=80, blank=True)
    producto = models.CharField(max_length=80, blank=True)
    titular = models.ForeignKey(
        Persona, null=True, blank=True, on_delete=models.SET_NULL, related_name="cuentas"
    )
    ultimos_digitos = models.CharField(max_length=4, blank=True)
    linea_credito = models.DecimalField(null=True, blank=True, **DINERO)
    tasa_anual = models.DecimalField(null=True, blank=True, **TASA)
    paga_total_mensual = models.BooleanField(null=True, blank=True)
    dia_corte = models.PositiveSmallIntegerField(null=True, blank=True, validators=DIA_DEL_MES)
    dia_pago = models.PositiveSmallIntegerField(null=True, blank=True, validators=DIA_DEL_MES)
    monto_inicial = models.DecimalField(null=True, blank=True, **DINERO)
    mensualidad = models.DecimalField(null=True, blank=True, **DINERO)
    saldo_actual = models.DecimalField(default=0, **DINERO)
    fecha_saldo = models.DateField(null=True, blank=True)
    activo = models.BooleanField(default=True)

    class Meta:
        ordering = ["nombre"]
        constraints = [
            models.UniqueConstraint(fields=["hogar", "nombre"], name="cuenta_nombre_unico")
        ]

    def __str__(self):
        return self.nombre


class Concepto(ModeloDeHogar):
    categoria = models.ForeignKey(Categoria, on_delete=models.RESTRICT, related_name="conceptos")
    nombre = models.CharField(max_length=80)
    es_fijo = models.BooleanField(default=False)
    es_hormiga = models.BooleanField(default=False)
    persona = models.ForeignKey(
        Persona,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        verbose_name="persona por defecto",
        help_text=AYUDA_SUGERIDO,
    )
    domicilio = models.ForeignKey(
        Domicilio,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        verbose_name="domicilio por defecto",
        help_text=(
            "Opcional. Distingue el mismo concepto en varios domicilios (ej. Luz de Casa Fidel) "
            "y se precarga al registrar un movimiento."
        ),
    )
    cuenta = models.ForeignKey(
        Cuenta,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        verbose_name="cuenta por defecto",
        help_text=AYUDA_SUGERIDO,
    )
    activo = models.BooleanField(default=True)

    class Meta:
        ordering = ["categoria__orden", "nombre"]
        constraints = [
            models.UniqueConstraint(
                fields=["categoria", "nombre", "domicilio"],
                name="concepto_unico_por_domicilio",
                nulls_distinct=False,
            )
        ]

    def __str__(self):
        return f"{self.nombre} ({self.domicilio})" if self.domicilio_id else self.nombre

    @property
    def nombre_con_categoria(self):
        return f"{self.categoria} › {self}"


class TasaMercado(ConMarcasDeTiempo):
    """Catálogo global de tasas promedio por tarjeta (de la hoja oculta del Excel)."""

    institucion = models.CharField(max_length=80)
    producto = models.CharField(max_length=80)
    tasa_promedio = models.DecimalField(**TASA)
    fecha_referencia = models.DateField(null=True, blank=True)

    class Meta:
        verbose_name = "tasa de mercado"
        verbose_name_plural = "tasas de mercado"
        ordering = ["institucion", "producto"]
        constraints = [
            models.UniqueConstraint(fields=["institucion", "producto"], name="tasa_mercado_unica")
        ]

    def __str__(self):
        return f"{self.institucion} — {self.producto}"
