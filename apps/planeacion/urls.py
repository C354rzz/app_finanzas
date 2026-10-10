from django.urls import path

from apps.planeacion import vistas

app_name = "planeacion"

urlpatterns = [
    path("metas/", vistas.metas, name="metas"),
    path("metas/nueva/", vistas.meta_nueva, name="meta_nueva"),
    path("metas/<int:pk>/", vistas.meta_editar, name="meta_editar"),
    path("metas/<int:pk>/eliminar/", vistas.meta_eliminar, name="meta_eliminar"),
]
