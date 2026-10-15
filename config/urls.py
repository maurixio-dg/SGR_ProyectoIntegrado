
from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views


urlpatterns = [
    # Administración interna
    path("admin/", admin.site.urls),

    # Autenticación
    path(
        "login/",
        auth_views.LoginView.as_view(
            template_name="login.html",
            redirect_authenticated_user=True
        ),
        name="login"
    ),

    path(
        "logout/",
        auth_views.LogoutView.as_view(),
        name="logout"
    ),

    # Módulos municipales
    path(
        "delegaciones/",
        include("delegaciones.urls")
    ),

    path(
        "catalogos/",
        include("catalogos.urls")
    ),

    path(
        "funcionarios/",
        include("funcionarios.urls")
    ),

    # Panel principal
    path(
        "",
        include("gestion.urls")
    ),

    # Gestión de usuarios
    path(
    "usuarios/",
    include("usuarios.urls")
),
]
