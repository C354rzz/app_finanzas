from django import forms
from django.urls import reverse
from django.utils import timezone

from apps.core.formularios import FormularioDeHogar
from apps.movimientos.models import INGRESOS_EXTRAORDINARIOS, TIPOS_DEUDA, MetodoPago, Movimiento


class FormularioMovimiento(FormularioDeHogar):
    tipo = None
    metodo_inicial = MetodoPago.EFECTIVO
    campos_sugeridos = ()

    class Meta:
        model = Movimiento
        fields = []
        widgets = {
            "monto": forms.NumberInput(
                attrs={"step": "0.01", "min": "0.01", "inputmode": "decimal", "autofocus": True}
            ),
            "fecha": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "notas": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance.tipo = self.tipo
        if not self.instance.pk:
            self.initial.setdefault("fecha", timezone.localdate())
            self.initial.setdefault("metodo_pago", self.metodo_inicial)

    def principales(self):
        return [campo for campo in self if campo.name not in self.campos_sugeridos]

    def sugeridos(self):
        return [campo for campo in self if campo.name in self.campos_sugeridos]


class FormularioGasto(FormularioMovimiento):
    tipo = Movimiento.Tipo.GASTO
    campos_sugeridos = ("metodo_pago", "cuenta", "persona", "domicilio", "es_hormiga")

    class Meta(FormularioMovimiento.Meta):
        fields = [
            "monto", "concepto", "categoria", "fecha", "descripcion", "notas",
            "metodo_pago", "cuenta", "persona", "domicilio", "es_hormiga",
        ]  # fmt: skip

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        concepto = self.fields["concepto"]
        concepto.queryset = concepto.queryset.select_related("categoria")
        concepto.label_from_instance = lambda c: c.nombre_con_categoria
        concepto.widget.attrs.update(
            {
                "hx-get": reverse("movimientos:sugeridos"),
                "hx-target": "#campos-sugeridos",
                "hx-trigger": "change",
                "hx-include": "this",
            }
        )
        self.fields["categoria"].help_text = "Si eliges un concepto, se usa su categoría."


class FormularioIngreso(FormularioMovimiento):
    tipo = Movimiento.Tipo.INGRESO
    metodo_inicial = MetodoPago.TRANSFERENCIA

    class Meta(FormularioMovimiento.Meta):
        fields = [
            "monto", "tipo_ingreso", "es_extraordinario", "fecha", "descripcion",
            "metodo_pago", "cuenta", "persona", "notas",
        ]  # fmt: skip
        labels = {"cuenta": "Cuenta destino"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        tipo_ingreso = self.fields["tipo_ingreso"]
        tipo_ingreso.required = True
        tipo_ingreso.widget.attrs["data-extraordinarios"] = " ".join(INGRESOS_EXTRAORDINARIOS)
        self.fields["es_extraordinario"].help_text = (
            "Aguinaldo, PTU, bonos…: cuentan en el ingreso real del mes, no en el promedio."
        )


class FormularioTransferencia(FormularioMovimiento):
    tipo = Movimiento.Tipo.TRANSFERENCIA
    metodo_inicial = MetodoPago.TRANSFERENCIA

    class Meta(FormularioMovimiento.Meta):
        fields = ["monto", "fecha", "cuenta", "cuenta_destino", "descripcion", "metodo_pago", "notas"]
        labels = {"cuenta": "De la cuenta", "cuenta_destino": "A la cuenta"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["cuenta"].required = True
        self.fields["cuenta_destino"].required = True


class FormularioPagoDeuda(FormularioTransferencia):
    tipo = Movimiento.Tipo.PAGO_DEUDA

    class Meta(FormularioTransferencia.Meta):
        labels = {"cuenta": "Pagar desde", "cuenta_destino": "Tarjeta o préstamo"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        destino = self.fields["cuenta_destino"]
        destino.queryset = destino.queryset.filter(tipo__in=TIPOS_DEUDA)


FORMULARIOS = {
    formulario.tipo: formulario
    for formulario in (
        FormularioGasto,
        FormularioIngreso,
        FormularioTransferencia,
        FormularioPagoDeuda,
    )
}
