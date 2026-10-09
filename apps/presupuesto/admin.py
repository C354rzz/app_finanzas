from django.contrib import admin

from apps.presupuesto.models import (
    PlantillaGasto,
    PlantillaIngreso,
    PlantillaPresupuesto,
    PresupuestoMes,
    PresupuestoMesGasto,
    PresupuestoMesIngreso,
)


class PlantillaIngresoInline(admin.TabularInline):
    model = PlantillaIngreso
    extra = 0
    exclude = ("hogar",)


class PlantillaGastoInline(admin.TabularInline):
    model = PlantillaGasto
    extra = 0
    exclude = ("hogar",)


@admin.register(PlantillaPresupuesto)
class PlantillaPresupuestoAdmin(admin.ModelAdmin):
    list_display = ("hogar", "porcentaje_ahorro")
    inlines = [PlantillaIngresoInline, PlantillaGastoInline]

    def save_formset(self, request, form, formset, change):
        for renglon in formset.save(commit=False):
            renglon.hogar = form.instance.hogar
            renglon.save()
        for renglon in formset.deleted_objects:
            renglon.delete()


class PresupuestoMesIngresoInline(admin.TabularInline):
    model = PresupuestoMesIngreso
    extra = 0
    exclude = ("hogar",)


class PresupuestoMesGastoInline(admin.TabularInline):
    model = PresupuestoMesGasto
    extra = 0
    exclude = ("hogar",)


@admin.register(PresupuestoMes)
class PresupuestoMesAdmin(admin.ModelAdmin):
    list_display = ("hogar", "anio", "mes", "porcentaje_ahorro", "cerrado")
    list_filter = ("hogar", "anio")
    inlines = [PresupuestoMesIngresoInline, PresupuestoMesGastoInline]
    save_formset = PlantillaPresupuestoAdmin.save_formset
