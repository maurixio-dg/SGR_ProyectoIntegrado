
from django.urls import path
from . import views

app_name = "delegaciones"

urlpatterns = [
    path(
        "",
        views.listar_delegaciones,
        name="listar"
    ),
    path(
        "nuevo/",
        views.crear_delegacion,
        name="crear"
    ),
    path(
        "<int:pk>/editar/",
        views.editar_delegacion,
        name="editar"
    ),
    path(
        "<int:pk>/eliminar/",
        views.eliminar_delegacion,
        name="eliminar"
    ),
]
