from django import forms

from apps.core.formularios import CampoPorcentaje, FormularioDeHogar
from apps.planeacion.models import MetaAhorro

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
