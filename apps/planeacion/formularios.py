import re
from decimal import Decimal

from django import forms
from django.core.exceptions import ValidationError

from apps.calculos.comun import CERO
from apps.calculos.credito import amortizar
from apps.core.formularios import CampoPorcentaje, FormularioDeHogar
from apps.planeacion.models import MESES_MAXIMOS, Activo, MetaAhorro

FECHA = forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")
PAGO_ANTICIPADO = re.compile(r"^\s*(\d{1,4})\s*[=:]\s*(\d[\d,]{0,20}(?:\.\d{1,2})?)\s*$")


class FormularioMeta(FormularioDeHogar):
    tasa_anual = CampoPorcentaje(
        label="Tasa de interés anual (%)", help_text="¿A qué tasa sueles invertir? 10 = 10 %."
    )

    class Meta:
        model = MetaAhorro
        fields = [
            "tipo", "nombre", "monto_objetivo", "ahorro_actual", "meses", "tasa_anual",
            "fecha_inicio", "cuenta", "activa",
        ]  # fmt: skip
        widgets = {"fecha_inicio": FECHA}


class FormularioActivo(FormularioDeHogar):
    class Meta:
        model = Activo
        fields = [
            "tipo",
            "nombre",
            "valor_actual",
            "fecha_valuacion",
            "domicilio",
            "cuenta",
            "activo",
        ]
        widgets = {"fecha_valuacion": FECHA}
        labels = {"activo": "Vigente (cuenta en el patrimonio)"}


class FormularioSimulador(forms.Form):
    """RF-SIM-01: datos del crédito. Tras is_valid() deja la tabla en `amortizacion`."""

    monto = forms.DecimalField(
        label="Crédito total", min_value=Decimal("0.01"), max_digits=12, decimal_places=2
    )
    tasa_anual = CampoPorcentaje(label="Tasa de interés anual (%)", maximo=Decimal("1000"))
    meses = forms.IntegerField(label="Duración en meses", min_value=1, max_value=MESES_MAXIMOS)
    comision_apertura = CampoPorcentaje(
        label="Comisión por apertura (%)", required=False, initial=Decimal("0")
    )
    pagos_anticipados = forms.CharField(
        label="Pagos anticipados",
        required=False,
        widget=forms.Textarea(attrs={"rows": 2, "placeholder": "3=5000"}),
        help_text="Uno por renglón: mes=monto (ej. 3=5000).",
    )
    nombre = forms.CharField(label="Nombre de la simulación", max_length=80, required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.amortizacion = None

    def clean_pagos_anticipados(self):
        pagos = {}
        for renglon in re.split(r"[\n;]+", self.cleaned_data["pagos_anticipados"]):
            if not renglon.strip():
                continue
            coincide = PAGO_ANTICIPADO.match(renglon)
            if not coincide:
                raise ValidationError(
                    f"No entiendo «{renglon.strip()}». Escribe mes=monto, por ejemplo 3=5000."
                )
            mes, monto = int(coincide[1]), Decimal(coincide[2].replace(",", ""))
            pagos[mes] = pagos.get(mes, CERO) + monto
        return pagos

    def clean(self):
        datos = super().clean()
        if not self.errors:
            try:
                self.amortizacion = amortizar(**self.argumentos())
            except ValueError as error:
                raise ValidationError(str(error)) from error
        return datos

    def argumentos(self):
        datos = self.cleaned_data
        return {
            "monto": datos["monto"],
            "tasa_anual": datos["tasa_anual"],
            "meses": datos["meses"],
            "comision_apertura": datos["comision_apertura"] or CERO,
            "pagos_anticipados": datos["pagos_anticipados"],
        }
