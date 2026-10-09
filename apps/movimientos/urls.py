from django.urls import path

from apps.movimientos import vistas

app_name = "movimientos"

urlpatterns = [
    path("capturar/<str:tipo>/", vistas.capturar, name="capturar"),
    path("sugeridos/", vistas.sugeridos, name="sugeridos"),
]
