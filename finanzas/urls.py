from django.contrib import admin
from django.urls import path

from finanzas.vistas import salud

urlpatterns = [
    path("admin/", admin.site.urls),
    path("salud/", salud, name="salud"),
]
