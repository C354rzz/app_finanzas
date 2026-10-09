from django.urls import path

from apps.tablero import vistas

app_name = "tablero"

urlpatterns = [
    path("<int:anio>/<int:mes>/", vistas.del_mes, name="mes"),
]
