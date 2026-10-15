
from django.contrib import admin
from .models import Delegacion


@admin.register(Delegacion)
class DelegacionAdmin(admin.ModelAdmin):
    list_display = ("id", "nombre", "estado")
    list_filter = ("estado",)
    search_fields = ("nombre",)
