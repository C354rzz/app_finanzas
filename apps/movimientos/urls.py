from django.urls import path

from apps.movimientos import vistas

app_name = "movimientos"

urlpatterns = [
    path("", vistas.inicio, name="inicio"),
    path("capturar/<str:tipo>/", vistas.capturar, name="capturar"),
    path("sugeridos/", vistas.sugeridos, name="sugeridos"),
    path("<int:anio>/<int:mes>/", vistas.lista, name="lista"),
    path("<int:anio>/<int:mes>/csv/", vistas.exportar_csv, name="csv_mes"),
    path("<int:anio>/csv/", vistas.exportar_csv, name="csv_anio"),
    path("<int:pk>/editar/", vistas.editar, name="editar"),
    path("<int:pk>/eliminar/", vistas.eliminar, name="eliminar"),
]
