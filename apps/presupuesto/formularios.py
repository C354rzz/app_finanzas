from django import forms

from apps.core.formularios import FormularioDeHogar
from apps.presupuesto.models import (
    PlantillaGasto,
    PlantillaIngreso,
    PresupuestoMesGasto,
    PresupuestoMesIngreso,
)

CAMPOS_INGRESO = ["nombre", "tipo_ingreso", "es_fijo", "monto", "persona"]
MARCAS_GASTO = ["es_fijo", "con_tarjeta", "es_hormiga"]


class FormularioRenglon(FormularioDeHogar):
    """Renglón de ingreso o gasto; `contenedor` es la plantilla o el presupuesto del mes."""

    contenedor_campo = ""

    def __init__(self, *args, contenedor, **kwargs):
        super().__init__(*args, **kwargs)
        setattr(self.instance, self.contenedor_campo, contenedor)
        if "concepto" in self.fields:
            concepto = self.fields["concepto"]
            concepto.queryset = concepto.queryset.select_related("categoria")
            concepto.label_from_instance = lambda c: c.nombre_con_categoria

    @property
    def campos_fijos(self):
        return ("hogar", self.contenedor_campo)


class FormularioIngresoPlantilla(FormularioRenglon):
    contenedor_campo = "plantilla"

    class Meta:
        model = PlantillaIngreso
        fields = CAMPOS_INGRESO


class FormularioGastoPlantilla(FormularioRenglon):
    contenedor_campo = "plantilla"

    class Meta:
        model = PlantillaGasto
        fields = ["concepto", "monto", "periodicidad", *MARCAS_GASTO]


class FormularioIngresoMes(FormularioRenglon):
    contenedor_campo = "presupuesto"

    class Meta:
        model = PresupuestoMesIngreso
        fields = CAMPOS_INGRESO


class FormularioGastoMes(FormularioRenglon):
    contenedor_campo = "presupuesto"

    class Meta:
        model = PresupuestoMesGasto
        fields = ["concepto", "monto_mensual", *MARCAS_GASTO]


RENGLONES = {
    ("plantilla", "ingreso"): FormularioIngresoPlantilla,
    ("plantilla", "gasto"): FormularioGastoPlantilla,
    ("mes", "ingreso"): FormularioIngresoMes,
    ("mes", "gasto"): FormularioGastoMes,
}


class FormularioPorcentaje(forms.Form):
    porcentaje = forms.DecimalField(
        label="% de ahorro",
        min_value=0,
        max_value=100,
        decimal_places=2,
        widget=forms.NumberInput(attrs={"list": "sugerencias-ahorro", "step": "0.01"}),
    )

    def fraccion(self):
        return self.cleaned_data["porcentaje"] / 100
