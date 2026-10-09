from django import forms

from apps.catalogos.models import Domicilio, Persona


class FormularioFiltrosTablero(forms.Form):
    persona = forms.ModelChoiceField(Persona.objects.none(), required=False, empty_label="Todas")
    domicilio = forms.ModelChoiceField(
        Domicilio.objects.none(), required=False, empty_label="Todos"
    )

    def __init__(self, *args, hogar, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["persona"].queryset = Persona.objects.del_hogar(hogar)
        self.fields["domicilio"].queryset = Domicilio.objects.del_hogar(hogar)

    def elegidos(self):
        """Persona y domicilio válidos; un id inválido o ajeno se ignora."""
        if not self.is_bound:
            return {"persona": None, "domicilio": None}
        self.is_valid()
        return {
            "persona": self.cleaned_data.get("persona"),
            "domicilio": self.cleaned_data.get("domicilio"),
        }
