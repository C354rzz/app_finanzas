from django.contrib import admin

from apps.planeacion.models import Activo, MetaAhorro, SimulacionCredito


@admin.register(MetaAhorro)
class MetaAhorroAdmin(admin.ModelAdmin):
    list_display = ("nombre", "tipo", "monto_objetivo", "ahorro_actual", "meses", "activa", "hogar")
    list_filter = ("hogar", "tipo", "activa")


@admin.register(Activo)
class ActivoAdmin(admin.ModelAdmin):
    list_display = ("nombre", "tipo", "valor_actual", "fecha_valuacion", "activo", "hogar")
    list_filter = ("hogar", "tipo", "activo")


@admin.register(SimulacionCredito)
class SimulacionCreditoAdmin(admin.ModelAdmin):
    list_display = ("nombre", "monto", "tasa_anual", "meses", "hogar")
    list_filter = ("hogar",)
