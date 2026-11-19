from django.contrib import admin
from .models import CatalogoMatrizSGR, ItemMatrizSGR, VinculoMatrizSGR

@admin.register(CatalogoMatrizSGR)
class CatalogoMatrizAdmin(admin.ModelAdmin):
    list_display = ('id', 'origen', 'nombre_archivo', 'fecha_importacion', 'importado_por')
    search_fields = ('nombre_archivo', 'origen')

@admin.register(ItemMatrizSGR)
class ItemMatrizAdmin(admin.ModelAdmin):
    list_display = ('nombre','hoja','fila','meta_original','ponderacion','clase')
    list_filter = ('clase','hoja')
    search_fields = ('nombre',)

@admin.register(VinculoMatrizSGR)
class VinculoMatrizAdmin(admin.ModelAdmin):
    list_display = ('item','meta','creado_en')
