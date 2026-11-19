from django.urls import path
from . import views
from . import views_especiales
from . import views_cargos
from . import views_valoraciones

app_name = 'matriz_sgr'
urlpatterns = [
    path('valoraciones/', views_valoraciones.listado, name='valoraciones'),
    path('valoraciones/nueva/', views_valoraciones.crear, name='valoracion_crear'),
    path('valoraciones/<int:pk>/', views_valoraciones.detalle, name='valoracion_detalle'),
    path('valoraciones/<int:pk>/respaldo/', views_valoraciones.respaldo, name='valoracion_respaldo'),
    path('especiales/', views_especiales.listado, name='especiales'),
    path('especiales/item/<int:pk>/crear/', views_especiales.crear, name='especial_crear'),
    path('especiales/<int:pk>/editar/', views_especiales.editar, name='especial_editar'),
    path('especiales/<int:pk>/respaldo/', views_especiales.descargar_respaldo, name='especial_respaldo'),
    path('', views.catalogos, name='catalogos'),
    path('importar/', views.importar, name='importar'),
    path('<int:pk>/cargos/', views_cargos.equivalencias, name='equivalencias'),
    path('<int:pk>/', views.detalle, name='detalle'),
    path('item/<int:pk>/vincular/', views.vincular, name='vincular'),
]
