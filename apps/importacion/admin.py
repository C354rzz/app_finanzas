from django.contrib import admin

from apps.importacion.models import Documento, MovimientoPropuesto, ReglaClasificacion


@admin.register(Documento)
class DocumentoAdmin(admin.ModelAdmin):
    list_display = ("nombre_original", "tipo", "emisor", "estado", "costo_estimado_usd", "hogar")
    list_filter = ("hogar", "estado", "tipo")
    readonly_fields = ("sha256", "modelo_ia", "tokens_entrada", "tokens_salida")


@admin.register(MovimientoPropuesto)
class MovimientoPropuestoAdmin(admin.ModelAdmin):
    list_display = ("fecha", "descripcion", "monto", "tipo", "estado", "documento")
    list_filter = ("hogar", "estado", "tipo")


@admin.register(ReglaClasificacion)
class ReglaClasificacionAdmin(admin.ModelAdmin):
    list_display = ("patron", "emisor", "categoria", "concepto", "prioridad", "veces_aplicada")
    list_filter = ("hogar",)
    search_fields = ("patron", "emisor")
