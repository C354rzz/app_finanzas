from django.urls import path

from apps.presupuesto import vistas

app_name = "presupuesto"

PLANTILLA = {"ambito": "plantilla"}
MES = {"ambito": "mes"}

urlpatterns = [
    path("", vistas.inicio, name="inicio"),
    path("plantilla/", vistas.plantilla, name="plantilla"),
    path("plantilla/porcentaje/", vistas.porcentaje, PLANTILLA, name="porcentaje_plantilla"),
    path("plantilla/<str:clase>/nuevo/", vistas.renglon_nuevo, PLANTILLA, name="nuevo_plantilla"),
    path("<int:anio>/<int:mes>/", vistas.del_mes, name="mes"),
    path("<int:anio>/<int:mes>/porcentaje/", vistas.porcentaje, MES, name="porcentaje_mes"),
    path("<int:anio>/<int:mes>/resincronizar/", vistas.resincronizar, name="resincronizar"),
    path("<int:anio>/<int:mes>/<str:clase>/nuevo/", vistas.renglon_nuevo, MES, name="nuevo_mes"),
    path(
        "renglon/<str:ambito>/<str:clase>/<int:pk>/", vistas.renglon_editar, name="editar_renglon"
    ),
    path(
        "renglon/<str:ambito>/<str:clase>/<int:pk>/eliminar/",
        vistas.renglon_eliminar,
        name="eliminar_renglon",
    ),
]
