
from django.urls import path
from . import views

app_name = "catalogos"

urlpatterns = [
    path(
        "cargos/",
        views.listar_cargos,
        name="listar_cargos"
    ),
    path(
        "cargos/nuevo/",
        views.crear_cargo,
        name="crear_cargo"
    ),
    path(
        "cargos/<int:pk>/editar/",
        views.editar_cargo,
        name="editar_cargo"
    ),
    path(
        "cargos/<int:pk>/eliminar/",
        views.eliminar_cargo,
        name="eliminar_cargo"
    ),
    
path(
    "funciones/",
    views.listar_funciones,
    name="listar_funciones"
),
path(
    "funciones/nueva/",
    views.crear_funcion,
    name="crear_funcion"
),
path(
    "funciones/<int:pk>/editar/",
    views.editar_funcion,
    name="editar_funcion"
),
path(
    "funciones/<int:pk>/estado/",
    views.cambiar_estado_funcion,
    name="cambiar_estado_funcion"
),

]
