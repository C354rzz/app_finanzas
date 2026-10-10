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
]
