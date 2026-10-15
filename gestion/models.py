
from django.db import models
from django.core.exceptions import ValidationError


class Periodo(models.Model):

    class Estado(models.TextChoices):
        PLANIFICADO = "PLAN", "Planificado"
        EN_CURSO = "CURSO", "En curso"
        FINALIZADO = "FIN", "Finalizado"

    nombre = models.CharField(
        max_length=150,
        unique=True
    )

    fecha_inicio = models.DateField()

    fecha_fin = models.DateField()

    estado = models.CharField(
        max_length=5,
        choices=Estado.choices,
        default=Estado.PLANIFICADO
    )

    descripcion = models.TextField(
        blank=True
    )

    class Meta:
        verbose_name = "Período"
        verbose_name_plural = "Períodos"
        ordering = ["-fecha_inicio"]

    def clean(self):
        super().clean()

        if (
            self.fecha_inicio
            and self.fecha_fin
            and self.fecha_fin < self.fecha_inicio
        ):
            raise ValidationError({
                "fecha_fin": (
                    "La fecha de término no puede ser "
                    "anterior a la fecha de inicio."
                )
            })

    def __str__(self):
        return self.nombre
