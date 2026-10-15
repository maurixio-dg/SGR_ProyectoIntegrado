
from django.urls import path
from . import views

app_name = "gestion"

urlpatterns = [

    # DASHBOARD
    path(
        "",
        views.dashboard,
        name="dashboard"
    ),

    # PERIODOS
    path(
        "periodos/",
        views.listar_periodos,
        name="listar_periodos"
    ),

    path(
        "periodos/nuevo/",
        views.crear_periodo,
        name="crear_periodo"
    ),

    path(
        "periodos/<int:pk>/editar/",
        views.editar_periodo,
        name="editar_periodo"
    ),

    path(
        "actividades/",
        views.listar_actividades,
        name="listar_actividades"
    ),
    path(
        "actividades/registrar/",
        views.registrar_actividad,
        name="registrar_actividad"
    ),

    path(
    "actividades/evidencias/",
    views.validar_evidencias,
    name="validar_evidencias"
    ),

    path(
    "agenda/",
    views.agenda_colectiva,
    name="agenda_colectiva"
    ),
   path(
    "agenda/<str:codigo>/",
    views.detalle_compromiso,
    name="detalle_compromiso"
   ),

   path(
    "indicadores/",
    views.indicadores,
    name="indicadores"
   ),

    path(
        "informes/",
        views.informes_gestion,
        name="informes_gestion"
    ),
]
