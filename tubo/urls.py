from django.urls import path
from . import views, integracion_metas

app_name='tubo'

urlpatterns=[
    path('',views.listar_gestiones,name='gestiones'),
    path('<int:pk>/vincular-meta/', integracion_metas.vincular_meta, name='vincular_meta'),
    path('nueva/',views.nueva_gestion,name='nueva_gestion'),
    path('<int:pk>/detalle/',views.detalle_gestion,name='detalle_gestion'),
    path('<int:pk>/editar/',views.editar_gestion,name='editar_gestion'),
    path('<int:pk>/hito/',views.anotar_hito,name='hito_gestion'),
    path('<int:pk>/resolver/',views.resolver_gestion,name='resolver_gestion'),
    path('vecinos/',views.vecinos,name='vecinos'),
    path('vecinos/nuevo/',views.formulario_vecino,name='nuevo_vecino'),
    path('vecinos/<int:pk>/editar/',views.formulario_vecino,name='editar_vecino'),
    path('vecinos/<int:pk>/eliminar/',views.eliminar_vecino,name='eliminar_vecino'),
    path('cartas/',views.cartas,name='cartas'),
    path('cartas/nueva/',views.formulario_carta,name='nueva_carta'),
    path('cartas/<int:pk>/detalle/',views.detalle_carta,name='detalle_carta'),
    path('cartas/<int:pk>/editar/',views.formulario_carta,name='editar_carta'),
    path('subtipos/',views.subtipos_por_tipo,name='subtipos_por_tipo'),
    path('archivo/<str:clase>/<int:pk>/',views.descargar_archivo,name='descargar_archivo'),
    path('catalogos/<str:clase>/',views.listar_catalogo,name='catalogo'),
    path('catalogos/<str:clase>/nuevo/',views.formulario_catalogo,name='nuevo_catalogo'),
    path('catalogos/<str:clase>/<int:pk>/editar/',views.formulario_catalogo,name='editar_catalogo'),
    path('catalogos/<str:clase>/<int:pk>/eliminar/',views.eliminar_catalogo,name='eliminar_catalogo'),
]
