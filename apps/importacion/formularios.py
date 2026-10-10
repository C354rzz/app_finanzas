from django import forms

from apps.catalogos.models import Cuenta
from apps.core.formularios import FormularioDeHogar
from apps.importacion.models import MovimientoPropuesto


class EntradaDeVariosArchivos(forms.ClearableFileInput):
    allow_multiple_selected = True


class CampoDeVariosArchivos(forms.FileField):
    """Acepta uno o varios archivos y siempre devuelve una lista."""

    def __init__(self, *args, **kwargs):
        kwargs.setdefault(
            "widget",
            EntradaDeVariosArchivos(attrs={"accept": ".pdf,.zip,application/pdf,application/zip"}),
        )
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        limpiar = super().clean
        if isinstance(data, (list, tuple)):
            return [limpiar(archivo, initial) for archivo in data]
        return [limpiar(data, initial)]


class FormularioSubida(forms.Form):
    archivos = CampoDeVariosArchivos(
        label="Archivos PDF o ZIP", help_text="Hasta 20 archivos de 20 MB cada uno."
    )
    cuenta = forms.ModelChoiceField(
        Cuenta.objects.none(),
        required=False,
        label="Cuenta (opcional)",
        help_text="Para estados de cuenta; si no la eliges, se busca por los últimos 4 dígitos.",
    )

    def __init__(self, *args, hogar, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["cuenta"].queryset = Cuenta.objects.del_hogar(hogar).filter(activo=True)


class FormularioPropuesta(FormularioDeHogar):
    class Meta:
        model = MovimientoPropuesto
        fields = [
            "fecha", "descripcion", "monto", "tipo", "tipo_ingreso", "es_extraordinario",
            "metodo_pago", "concepto", "categoria", "cuenta", "cuenta_destino", "persona",
            "domicilio", "es_hormiga",
        ]  # fmt: skip
        widgets = {"fecha": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        concepto = self.fields["concepto"]
        concepto.queryset = concepto.queryset.select_related("categoria")
        concepto.label_from_instance = lambda c: c.nombre_con_categoria
