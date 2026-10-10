from django.contrib import admin
from django.urls import include, path

from finanzas.vistas import salud

urlpatterns = [
    path("admin/", admin.site.urls),
    path("salud/", salud, name="salud"),
    path("movimientos/", include("apps.movimientos.urls")),
    path("presupuesto/", include("apps.presupuesto.urls")),
    path("tablero/", include("apps.tablero.urls")),
    path("catalogos/", include("apps.catalogos.urls")),
    path("planeacion/", include("apps.planeacion.urls")),
    path("importar/", include("apps.importacion.urls")),
    path("", include("apps.core.urls")),
]
