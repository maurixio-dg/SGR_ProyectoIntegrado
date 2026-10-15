
from django.db import models


class Cargo(models.Model):
    nombre_cargo = models.CharField(
        max_length=150,
        unique=True
    )

    descripcion = models.TextField(
        blank=True
    )

    class Meta:
        verbose_name = "Cargo"
        verbose_name_plural = "Cargos"
        ordering = ["nombre_cargo"]

    def __str__(self):
        return self.nombre_cargo


class Funcion(models.Model):

    cargo = models.ForeignKey(
        "catalogos.Cargo",
        on_delete=models.PROTECT,
        related_name="funciones"
    )

    nombre = models.CharField(
        max_length=150
    )

    descripcion = models.TextField(
        blank=True
    )

    estado = models.BooleanField(
        default=True
    )

    class Meta:
        verbose_name = "Función"
        verbose_name_plural = "Funciones"
        ordering = ["cargo__nombre_cargo", "nombre"]

        constraints = [
            models.UniqueConstraint(
                fields=["cargo", "nombre"],
                name="unique_funcion_por_cargo"
            )
        ]

    def __str__(self):
        return f"{self.nombre} - {self.cargo.nombre_cargo}"
