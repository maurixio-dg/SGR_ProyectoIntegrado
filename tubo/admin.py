from django.contrib import admin
from .models import Territorio, TipoAtencion, SubtipoAtencion, Vecino


@admin.register(Territorio)
class TerritorioAdmin(admin.ModelAdmin):
    list_display=('nombre','delegacion','activo')
    list_filter=('delegacion','activo')


@admin.register(TipoAtencion)
class TipoAtencionAdmin(admin.ModelAdmin):
    list_display=('nombre','activo')
    list_filter=('activo',)


@admin.register(SubtipoAtencion)
class SubtipoAtencionAdmin(admin.ModelAdmin):
    list_display=('nombre','tipo','activo')
    list_filter=('tipo','activo')


@admin.register(Vecino)
class VecinoAdmin(admin.ModelAdmin):
    list_display=('nombre','rut','delegacion')
    search_fields=('nombre','rut')
    list_filter=('delegacion',)

# No se registran Gestiones ni Cartas en Django Admin para impedir saltarse
# las reglas de propiedad, aprobacion y cierre de la interfaz municipal.
