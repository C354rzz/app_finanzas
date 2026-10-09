from django import forms
from django.core.exceptions import NON_FIELD_ERRORS
from django.db.models import Q

from apps.core.models import ModeloDeHogar


class FormularioDeHogar(forms.ModelForm):
    """ModelForm de un dato del hogar.

    - Cada lista desplegable muestra solo registros del hogar y activos (al editar conserva el
      valor actual aunque esté inactivo).
    - Valida las restricciones únicas que incluyen los `campos_fijos` (hogar, contenedor), que
      Django omitiría por no estar en el formulario.
    - Un error del modelo sobre un campo que no está en el formulario se muestra como general.
    """

    campos_fijos = ("hogar",)

    def __init__(self, *args, hogar, **kwargs):
        super().__init__(*args, **kwargs)
        self.hogar = hogar
        self.instance.hogar = hogar
        for nombre, campo in self.fields.items():
            if not isinstance(campo, forms.ModelChoiceField):
                continue
            modelo = campo.queryset.model
            if not issubclass(modelo, ModeloDeHogar):
                continue
            consulta = campo.queryset.filter(hogar=hogar)
            if any(f.name == "activo" for f in modelo._meta.fields):
                actual = self.initial.get(nombre)
                consulta = (
                    consulta.filter(Q(activo=True) | Q(pk=actual))
                    if actual
                    else consulta.filter(activo=True)
                )
            campo.queryset = consulta

    def _get_validation_exclusions(self):
        return super()._get_validation_exclusions() - set(self.campos_fijos)

    def add_error(self, field, error):
        if field is None and hasattr(error, "error_dict"):
            for nombre in [
                n for n in error.error_dict if n != NON_FIELD_ERRORS and n not in self.fields
            ]:
                error.error_dict.setdefault(NON_FIELD_ERRORS, []).extend(
                    error.error_dict.pop(nombre)
                )
        super().add_error(field, error)
