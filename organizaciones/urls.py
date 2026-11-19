from django.urls import path
from . import views

app_name = 'organizaciones'

urlpatterns = [
    path('', views.listar, name='listar'),
    path('nueva/', views.crear, name='crear'),
    path('importar/', views.importar_excel, name='importar'),
    path('<int:pk>/editar/', views.editar, name='editar'),
    path('<int:pk>/eliminar/', views.eliminar, name='eliminar'),
]
