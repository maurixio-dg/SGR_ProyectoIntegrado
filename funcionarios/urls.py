
from django.urls import path
from . import views

app_name = "funcionarios"

urlpatterns = [
    path(
        "",
        views.listar_funcionarios,
        name="listar"
    ),

    path(
        "nuevo/",
        views.crear_funcionario,
        name="crear"
    ),

    path(
        "<int:pk>/editar/",
        views.editar_funcionario,
        name="editar"
    ),

    path(
        "<int:pk>/eliminar/",
        views.eliminar_funcionario,
        name="eliminar"
    ),
]
