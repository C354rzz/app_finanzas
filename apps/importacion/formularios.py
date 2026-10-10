from django import forms

from apps.catalogos.models import Cuenta


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
