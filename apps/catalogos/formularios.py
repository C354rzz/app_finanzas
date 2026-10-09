from django import forms

from apps.catalogos.models import Categoria, Concepto, Cuenta, Domicilio, Persona
from apps.core.formularios import FormularioDeHogar


class FormularioCatalogo(FormularioDeHogar):
    """`grupos` = [(título, ayuda, [campos])]; sin grupos, los campos van en orden."""

    grupos = None

    def secciones(self):
        if not self.grupos:
            return []
        return [(titulo, ayuda, [self[c] for c in campos]) for titulo, ayuda, campos in self.grupos]


class FormularioPersona(FormularioCatalogo):
    class Meta:
        model = Persona
        fields = ["nombre", "parentesco", "activo"]


class FormularioDomicilio(FormularioCatalogo):
    class Meta:
        model = Domicilio
        fields = ["alias", "direccion", "activo"]


class FormularioCategoria(FormularioCatalogo):
    class Meta:
        model = Categoria
        fields = ["nombre", "icono", "orden", "activo"]


class FormularioConcepto(FormularioCatalogo):
    grupos = [
        (None, None, ["categoria", "nombre", "es_fijo", "es_hormiga", "activo"]),
        (
            "Valores sugeridos (opcional)",
            "Se precargan al registrar un movimiento; puedes cambiarlos en cada gasto.",
            ["persona", "cuenta", "domicilio"],
        ),
    ]

    class Meta:
        model = Concepto
        fields = [
            "categoria", "nombre", "es_fijo", "es_hormiga", "activo",
            "persona", "cuenta", "domicilio",
        ]  # fmt: skip


class FormularioCuenta(FormularioCatalogo):
    grupos = [
        (None, None, ["nombre", "tipo", "institucion", "producto", "titular", "ultimos_digitos",
                      "activo"]),
        (
            "Tarjeta de crédito",
            "Solo para tarjetas. Si no capturas la tasa, se usa el promedio del mercado.",
            ["linea_credito", "tasa_anual", "paga_total_mensual", "dia_corte", "dia_pago"],
        ),
        ("Préstamo", None, ["monto_inicial", "mensualidad"]),
        (
            "Saldo",
            "Positivo = lo que tienes (débito, efectivo) o lo que debes (crédito, préstamo).",
            ["saldo_actual", "fecha_saldo"],
        ),
    ]  # fmt: skip

    class Meta:
        model = Cuenta
        fields = [
            "nombre", "tipo", "institucion", "producto", "titular", "ultimos_digitos", "activo",
            "linea_credito", "tasa_anual", "paga_total_mensual", "dia_corte", "dia_pago",
            "monto_inicial", "mensualidad", "saldo_actual", "fecha_saldo",
        ]  # fmt: skip
        widgets = {"fecha_saldo": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")}
