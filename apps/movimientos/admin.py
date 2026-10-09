from django.contrib import admin

from apps.movimientos.models import Movimiento
from apps.movimientos.servicios import eliminar_movimiento, guardar_movimiento


@admin.register(Movimiento)
class MovimientoAdmin(admin.ModelAdmin):
    list_display = ("fecha", "tipo", "descripcion", "categoria", "monto", "metodo_pago", "cuenta")
    list_filter = ("hogar", "tipo", "metodo_pago", "categoria")
    search_fields = ("descripcion", "notas")
    date_hierarchy = "fecha"

    def save_model(self, request, obj, form, change):
        guardar_movimiento(obj, usuario=request.user)

    def delete_model(self, request, obj):
        eliminar_movimiento(obj)

    def get_actions(self, request):
        # El borrado masivo no pasaría por eliminar_movimiento (RN-14).
        acciones = super().get_actions(request)
        acciones.pop("delete_selected", None)
        return acciones
