
from django.contrib import admin
from .models import Cargo


@admin.register(Cargo)
class CargoAdmin(admin.ModelAdmin):
    list_display = ("id", "nombre_cargo", "descripcion")
    search_fields = ("nombre_cargo",)



from .models import Funcion


@admin.register(Funcion)
class FuncionAdmin(admin.ModelAdmin):

    list_display = (
        "nombre",
        "cargo",
        "estado",
    )

    list_filter = (
        "cargo",
        "estado",
    )

    search_fields = (
        "nombre",
        "cargo__nombre_cargo",
    )
