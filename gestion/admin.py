
from django.contrib import admin

from .models import Periodo


@admin.register(Periodo)
class PeriodoAdmin(admin.ModelAdmin):

    list_display = (
        "nombre",
        "fecha_inicio",
        "fecha_fin",
        "estado",
    )

    list_filter = (
        "estado",
        "fecha_inicio",
    )

    search_fields = (
        "nombre",
        "descripcion",
    )
