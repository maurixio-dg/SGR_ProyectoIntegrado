
from django.db import models


class Delegacion(models.Model):
    nombre = models.CharField(
        max_length=150,
        unique=True
    )

    estado = models.BooleanField(
        default=True
    )

    class Meta:
        verbose_name = "Delegación"
        verbose_name_plural = "Delegaciones"
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre
