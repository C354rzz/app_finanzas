from django import forms

from apps.core.formularios import CampoPorcentaje, FormularioDeHogar
from apps.planeacion.models import Activo, MetaAhorro

FECHA = forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")


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
