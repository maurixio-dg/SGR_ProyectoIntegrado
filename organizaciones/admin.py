from django.contrib import admin
from .models import OrganizacionComunitaria


@admin.register(OrganizacionComunitaria)
class OrganizacionComunitariaAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'tipo', 'territorio_origen', 'delegacion',
                    'estado_verificacion', 'numero_registro_pj')
    list_filter = ('tipo', 'estado_verificacion', 'delegacion', 'territorio_origen')
    search_fields = ('nombre', 'domicilio_legal', 'numero_registro_pj')
    readonly_fields = ('fuente_archivo', 'fila_origen', 'creado_por', 'creado_en', 'actualizado_en')
    list_per_page = 35
