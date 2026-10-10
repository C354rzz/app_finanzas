from django.urls import path

from apps.importacion import vistas

app_name = "importacion"

urlpatterns = [
    path("", vistas.importar, name="importar"),
    path("documentos/", vistas.documentos, name="documentos"),
    path("<int:pk>/", vistas.revisar, name="revisar"),
    path("<int:pk>/original/", vistas.original, name="original"),
    path("<int:pk>/reintentar/", vistas.reintentar, name="reintentar"),
    path("<int:pk>/eliminar/", vistas.eliminar, name="eliminar"),
    path("<int:pk>/aceptar-todo/", vistas.aceptar_todo, name="aceptar_todo"),
    path("<int:pk>/descartar-todo/", vistas.descartar_todo, name="descartar_todo"),
    path("<int:pk>/saldo/", vistas.actualizar_saldo, name="saldo"),
    path("propuesta/<int:pk>/", vistas.propuesta_editar, name="editar"),
    path("propuesta/<int:pk>/aceptar/", vistas.propuesta_aceptar, name="aceptar"),
    path("propuesta/<int:pk>/descartar/", vistas.propuesta_descartar, name="descartar"),
]
