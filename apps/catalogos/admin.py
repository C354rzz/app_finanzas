from django.contrib import admin

from apps.catalogos.models import Categoria, Concepto, Cuenta, Domicilio, Persona, TasaMercado


@admin.register(Persona)
class PersonaAdmin(admin.ModelAdmin):
    list_display = ("nombre", "parentesco", "activo", "hogar")
    list_filter = ("hogar", "activo")


@admin.register(Domicilio)
class DomicilioAdmin(admin.ModelAdmin):
    list_display = ("alias", "direccion", "activo", "hogar")
    list_filter = ("hogar", "activo")


@admin.register(Categoria)
class CategoriaAdmin(admin.ModelAdmin):
    list_display = ("nombre", "icono", "orden", "activo", "hogar")
    list_filter = ("hogar", "activo")


@admin.register(Concepto)
class ConceptoAdmin(admin.ModelAdmin):
    list_display = ("nombre", "categoria", "domicilio", "persona", "es_fijo", "es_hormiga")
    list_filter = ("hogar", "categoria", "domicilio", "es_fijo", "es_hormiga")
    search_fields = ("nombre",)
    fieldsets = (
        (None, {"fields": ("hogar", "categoria", "nombre", "es_fijo", "es_hormiga", "activo")}),
        (
            "Valores sugeridos (opcional)",
            {
                "description": (
                    "Se precargan al registrar un movimiento; puedes cambiarlos en cada gasto."
                ),
                "fields": ("persona", "cuenta", "domicilio"),
            },
        ),
    )


@admin.register(Cuenta)
class CuentaAdmin(admin.ModelAdmin):
    list_display = ("nombre", "tipo", "institucion", "saldo_actual", "linea_credito", "activo")
    list_filter = ("hogar", "tipo", "activo")


@admin.register(TasaMercado)
class TasaMercadoAdmin(admin.ModelAdmin):
    list_display = ("institucion", "producto", "tasa_promedio", "fecha_referencia")
    search_fields = ("institucion", "producto")
