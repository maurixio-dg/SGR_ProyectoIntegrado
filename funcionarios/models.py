
from django.conf import settings
from django.db import models


class Funcionario(models.Model):

    delegacion = models.ForeignKey(
        "delegaciones.Delegacion",
        on_delete=models.PROTECT,
        related_name="funcionarios"
    )

    cargo = models.ForeignKey(
        "catalogos.Cargo",
        on_delete=models.PROTECT,
        related_name="funcionarios"
    )

    rut = models.CharField(
        max_length=12,
        unique=True
    )

    nombre = models.CharField(max_length=100)
    email = models.EmailField(
    max_length=150,
    unique=True
)

    usuario = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="funcionario"
    )

    class Meta:
        verbose_name = "Funcionario"
        verbose_name_plural = "Funcionarios"
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre
