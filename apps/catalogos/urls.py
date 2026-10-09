from django.urls import path

from apps.catalogos import vistas

app_name = "catalogos"

urlpatterns = [
    path("", vistas.indice, name="indice"),
    path("<str:catalogo>/", vistas.lista, name="lista"),
    path("<str:catalogo>/nuevo/", vistas.nuevo, name="nuevo"),
    path("<str:catalogo>/<int:pk>/", vistas.editar, name="editar"),
    path("<str:catalogo>/<int:pk>/eliminar/", vistas.eliminar, name="eliminar"),
]
