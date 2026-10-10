from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models

from apps.catalogos.models import DINERO, Categoria, Concepto, Cuenta, Domicilio, Persona
from apps.core.models import ModeloDeHogar
from apps.movimientos.models import MetodoPago, Movimiento, TipoIngreso


def ruta_documento(documento, _nombre):
    """Los PDFs se guardan por hogar y por huella; nunca con el nombre original."""
    return f"documentos/{documento.hogar_id}/{documento.sha256}.pdf"


class Documento(ModeloDeHogar):
    class Tipo(models.TextChoices):
        ESTADO_CUENTA = "estado_cuenta", "Estado de cuenta"
        NOMINA = "nomina", "Recibo de nómina"
        RECIBO_SERVICIO = "recibo_servicio", "Recibo de servicio"
        OTRO = "otro", "Otro"

    class Estado(models.TextChoices):
        SUBIDO = "subido", "Subido"
        PROCESANDO = "procesando", "Procesando"
        POR_REVISAR = "por_revisar", "Por revisar"
        CONFIRMADO = "confirmado", "Confirmado"
        DESCARTADO = "descartado", "Descartado"
        ERROR = "error", "Error"

    ESTADOS_EN_CURSO = (Estado.SUBIDO, Estado.PROCESANDO)

    archivo = models.FileField(upload_to=ruta_documento, max_length=255)
    nombre_original = models.CharField("nombre original", max_length=255)
    sha256 = models.CharField(max_length=64)
    tipo = models.CharField(max_length=20, choices=Tipo.choices, blank=True)
    emisor = models.CharField(max_length=80, blank=True)
    cuenta = models.ForeignKey(
        Cuenta, null=True, blank=True, on_delete=models.SET_NULL, related_name="documentos"
    )
    periodo_inicio = models.DateField(null=True, blank=True)
    periodo_fin = models.DateField(null=True, blank=True)
    saldo_al_corte = models.DecimalField("saldo al corte", null=True, blank=True, **DINERO)
    paginas = models.PositiveSmallIntegerField("páginas", null=True, blank=True)
    estado = models.CharField(max_length=12, choices=Estado.choices, default=Estado.SUBIDO)
    error = models.TextField(blank=True)
    aviso = models.CharField(max_length=255, blank=True)
    modelo_ia = models.CharField("modelo de IA", max_length=40, blank=True)
    tokens_entrada = models.PositiveIntegerField(null=True, blank=True)
    tokens_salida = models.PositiveIntegerField(null=True, blank=True)
    costo_estimado_usd = models.DecimalField(
        "costo estimado (USD)", max_digits=8, decimal_places=4, null=True, blank=True
    )
    subido_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )

    class Meta:
        verbose_name = "documento"
        verbose_name_plural = "documentos"
        ordering = ["-creado_en"]
        constraints = [
            models.UniqueConstraint(fields=["hogar", "sha256"], name="documento_unico_por_hogar")
        ]

    def __str__(self):
        return self.nombre_original


class ReglaClasificacion(ModeloDeHogar):
    patron = models.CharField(
        "patrón",
        max_length=120,
        help_text="Palabras que contiene la descripción (sin mayúsculas ni acentos), ej. «oxxo».",
    )
    emisor = models.CharField(
        max_length=80, blank=True, help_text="Opcional: aplica solo a documentos de este emisor."
    )
    categoria = models.ForeignKey(
        Categoria, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    concepto = models.ForeignKey(
        Concepto, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    persona = models.ForeignKey(
        Persona, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    domicilio = models.ForeignKey(
        Domicilio, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    es_hormiga = models.BooleanField("hormiga 🐜", null=True, blank=True)
    prioridad = models.PositiveSmallIntegerField(default=100)
    veces_aplicada = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = "regla de clasificación"
        verbose_name_plural = "reglas de clasificación"
        ordering = ["prioridad", "patron"]

    def __str__(self):
        return self.patron


class MovimientoPropuesto(ModeloDeHogar):
    class Estado(models.TextChoices):
        PENDIENTE = "pendiente", "Pendiente"
        ACEPTADO = "aceptado", "Aceptado"
        DESCARTADO = "descartado", "Descartado"

    documento = models.ForeignKey(Documento, on_delete=models.CASCADE, related_name="propuestas")
    fecha = models.DateField()
    descripcion_original = models.CharField("descripción original", max_length=255)
    descripcion = models.CharField("descripción", max_length=255)
    monto = models.DecimalField(validators=[MinValueValidator(Decimal("0.01"))], **DINERO)
    tipo = models.CharField(max_length=15, choices=Movimiento.Tipo.choices)
    tipo_ingreso = models.CharField(
        "tipo de ingreso", max_length=20, choices=TipoIngreso.choices, blank=True
    )
    es_extraordinario = models.BooleanField("extraordinario", default=False)
    metodo_pago = models.CharField(
        "método de pago", max_length=15, choices=MetodoPago.choices, default=MetodoPago.EFECTIVO
    )
    categoria = models.ForeignKey(
        Categoria, null=True, blank=True, on_delete=models.SET_NULL, related_name="+",
        verbose_name="categoría",
    )  # fmt: skip
    concepto = models.ForeignKey(
        Concepto, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    persona = models.ForeignKey(
        Persona, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    domicilio = models.ForeignKey(
        Domicilio, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    cuenta = models.ForeignKey(
        Cuenta, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    cuenta_destino = models.ForeignKey(
        Cuenta, null=True, blank=True, on_delete=models.SET_NULL, related_name="+",
        verbose_name="cuenta destino",
    )  # fmt: skip
    es_hormiga = models.BooleanField("hormiga 🐜", default=False)
    confianza = models.DecimalField(max_digits=3, decimal_places=2, null=True, blank=True)
    regla = models.ForeignKey(
        ReglaClasificacion, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="propuestas",
    )  # fmt: skip
    posible_duplicado_de = models.ForeignKey(
        Movimiento, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    estado = models.CharField(max_length=10, choices=Estado.choices, default=Estado.PENDIENTE)
    movimiento = models.OneToOneField(
        Movimiento, null=True, blank=True, on_delete=models.SET_NULL, related_name="propuesta"
    )
    error = models.TextField(blank=True)

    class Meta:
        verbose_name = "movimiento propuesto"
        verbose_name_plural = "movimientos propuestos"
        ordering = ["fecha", "id"]

    def __str__(self):
        return f"{self.fecha:%d/%m/%Y} {self.descripcion} {self.monto}"
