
from django.contrib.auth.models import AbstractUser
from django.db import models


class Usuario(AbstractUser):

    class Rol(models.TextChoices):
        ADMINISTRADOR = "ADMIN", "Administrador"
        COORDINADOR = "COORD", "Coordinador"
        DELEGADO = "DELEG", "Delegado"
        FUNCIONARIO = "FUNC", "Funcionario"
        VERIFICADOR = "VERIF", "Verificador"
        CONSULTA = "CONS", "Usuario de consulta"

    rol = models.CharField(
        max_length=5,
        choices=Rol.choices,
        default=Rol.FUNCIONARIO
    )

    class Meta:
        verbose_name = "Usuario"
        verbose_name_plural = "Usuarios"

    def __str__(self):
        return self.username
