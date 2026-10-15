
from django.contrib import admin
from .models import Funcionario


@admin.register(Funcionario)
class FuncionarioAdmin(admin.ModelAdmin):
    list_display = (
        "rut",
        "nombre",
        "delegacion",
        "cargo",
        "email",
    )

    search_fields = ("rut", "nombre", "email")

    list_filter = ("delegacion", "cargo")
