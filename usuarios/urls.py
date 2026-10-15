
from django.urls import path
from . import views

app_name = "usuarios"

urlpatterns = [
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
