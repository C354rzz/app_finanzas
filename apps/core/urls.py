from django.contrib.auth import views as auth
from django.urls import path

from apps.core import vistas
from apps.core.formularios import FormularioEntrada

urlpatterns = [
    path("", vistas.inicio, name="inicio"),
    path(
        "entrar/",
        auth.LoginView.as_view(
            template_name="core/entrar.html",
            authentication_form=FormularioEntrada,
            redirect_authenticated_user=True,
        ),
        name="login",
    ),
    path("salir/", auth.LogoutView.as_view(), name="logout"),
]
