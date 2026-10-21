
from django.urls import path
from . import views

app_name = "usuarios"

urlpatterns = [
    path("mi-perfil/", views.mi_perfil, name="mi_perfil"),
    path("mi-perfil/contrasena/", views.cambiar_mi_password, name="cambiar_mi_password"),
    path(
        "",
        views.listar_usuarios,
        name="listar"
    ),

    path(
        "nuevo/",
        views.crear_usuario,
        name="crear"
    ),

    path(
        "<int:pk>/editar/",
        views.editar_usuario,
        name="editar"
    ),

    path(
        "<int:pk>/desactivar/",
        views.desactivar_usuario,
        name="desactivar"
    ),

    path(
        "<int:pk>/activar/",
        views.activar_usuario,
        name="activar"
    ),
]
