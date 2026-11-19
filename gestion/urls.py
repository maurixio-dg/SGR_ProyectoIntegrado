
from django.urls import path
from . import views
from . import operativa_eva3
from . import medicion_eva3
from . import actividades_eva3

app_name = "gestion"

urlpatterns = [
    path("actividades/<int:pk>/detalle/", actividades_eva3.detalle_actividad, name="detalle_actividad"),
    path("indicadores/ponderaciones/", medicion_eva3.auditoria_ponderaciones, name="auditoria_ponderaciones"),
    path("indicadores/ausencias/", medicion_eva3.listar_ausencias_sgr, name="ausencias_sgr"),
    path("indicadores/ausencias/nueva/", medicion_eva3.registrar_ausencia_sgr, name="registrar_ausencia_sgr"),
    path("indicadores/ausencias/<int:pk>/eliminar/", medicion_eva3.eliminar_ausencia_sgr, name="eliminar_ausencia_sgr"),
    path("indicadores/<int:pk>/configurar/", medicion_eva3.configurar_meta_sgr, name="configurar_meta_sgr"),
    # EVA 3: rutas específicas antes de agenda/<str:codigo>/.
    path("agenda/nuevo/", operativa_eva3.nuevo_compromiso, name="nuevo_compromiso"),
    path("agenda/<int:pk>/editar/", operativa_eva3.editar_compromiso, name="editar_compromiso"),
    path("agenda/<int:pk>/eliminar/", operativa_eva3.eliminar_compromiso, name="eliminar_compromiso"),
    path("indicadores/nueva/", operativa_eva3.nueva_meta, name="nueva_meta"),
    path("indicadores/<int:pk>/editar/", operativa_eva3.editar_meta, name="editar_meta"),
    path("actividades/<int:pk>/resolver/", operativa_eva3.resolver_actividad, name="resolver_actividad"),
    path("informes/exportar/csv/", operativa_eva3.exportar_informe_csv, name="exportar_informe_csv"),
    path("actividades/<int:pk>/editar/", actividades_eva3.editar_actividad, name="editar_actividad"),
    path("actividades/<int:pk>/evidencia/", actividades_eva3.descargar_evidencia, name="descargar_evidencia_actividad"),

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
        actividades_eva3.listar_actividades,
        name="listar_actividades"
    ),
    path(
        "actividades/registrar/",
        actividades_eva3.registrar_actividad,
        name="registrar_actividad"
    ),

    path(
    "actividades/evidencias/",
    operativa_eva3.validar_evidencias,
    name="validar_evidencias"
    ),

    path(
    "agenda/",
    operativa_eva3.agenda_colectiva,
    name="agenda_colectiva"
    ),
   path(
    "agenda/<str:codigo>/",
    operativa_eva3.detalle_compromiso,
    name="detalle_compromiso"
   ),

   path(
    "indicadores/",
    operativa_eva3.indicadores,
    name="indicadores"
   ),

    path(
        "informes/",
        operativa_eva3.informes_gestion,
        name="informes_gestion"
    ),
]
