from django.urls import path

from apps.planeacion import vistas

app_name = "planeacion"

urlpatterns = [
    path("metas/", vistas.metas, name="metas"),
    path("metas/nueva/", vistas.meta_nueva, name="meta_nueva"),
    path("metas/<int:pk>/", vistas.meta_editar, name="meta_editar"),
    path("metas/<int:pk>/eliminar/", vistas.meta_eliminar, name="meta_eliminar"),
    path("deudas/", vistas.deudas, name="deudas"),
    path("patrimonio/", vistas.patrimonio, name="patrimonio"),
    path("patrimonio/nuevo/", vistas.activo_nuevo, name="activo_nuevo"),
    path("patrimonio/<int:pk>/", vistas.activo_editar, name="activo_editar"),
    path("patrimonio/<int:pk>/eliminar/", vistas.activo_eliminar, name="activo_eliminar"),
]
