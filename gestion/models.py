
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

# ============================================================
# EVALUACION 3 — REGISTRO OPERATIVO DE ACTIVIDADES
# ============================================================
from datetime import timedelta
from django.conf import settings
from django.utils import timezone


class Actividad(models.Model):
    class TipoAccion(models.TextChoices):
        EJECUTADA = "EJEC", "Acción ejecutada"
        COORDINACION = "COORD", "Coordinación / gestión preparatoria"

    class Estado(models.TextChoices):
        REGISTRADA = "REG", "Registrada"
        EN_REVISION = "REV", "En revisión"
        APROBADA = "APR", "Aprobada"
        RECHAZADA = "RECH", "Rechazada"

    fecha_actividad = models.DateField("Fecha de actividad")
    delegacion = models.ForeignKey(
        "delegaciones.Delegacion", on_delete=models.PROTECT,
        related_name="actividades_operativas",
    )
    funcionario = models.ForeignKey(
        "funcionarios.Funcionario", on_delete=models.PROTECT,
        related_name="actividades_operativas",
    )
    periodo = models.ForeignKey(
        "gestion.Periodo", on_delete=models.PROTECT,
        null=True, blank=True, related_name="actividades_operativas",
    )
    tipo_accion = models.CharField(
        max_length=5, choices=TipoAccion.choices, default=TipoAccion.EJECUTADA,
    )
    titulo = models.CharField("Actividad o solicitud", max_length=200)
    descripcion = models.TextField("Descripción", blank=True)
    accion_realizada = models.TextField("Acción realizada")
    nombre_solicitante = models.CharField(
        "Nombre de la persona solicitante", max_length=150, blank=True,
    )
    telefono_solicitante = models.CharField(
        "Teléfono de la persona solicitante", max_length=25, blank=True,
    )
    solicitante_es_delegado = models.BooleanField(
        "La persona solicitante es el delegado", default=False,
    )
    evidencia = models.FileField(
        "Archivo de evidencia", upload_to="actividades_eva3/", blank=True,
    )
    estado = models.CharField(
        max_length=4, choices=Estado.choices, default=Estado.REGISTRADA,
    )
    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name="actividades_registradas",
    )
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-fecha_actividad", "-creado_en"]
        verbose_name = "Actividad operativa"
        verbose_name_plural = "Actividades operativas"

    def __str__(self):
        return f"{self.titulo} — {self.fecha_actividad}"

    @property
    def codigo(self):
        return f"SGR-ACT-{self.pk:06d}" if self.pk else "SIN GUARDAR"

    @property
    def elegible_para_puntaje(self):
        # Solo determina elegibilidad: el puntaje ponderado se implementará
        # al definir los ítems y sus metas con la matriz municipal.
        return bool(
            self.estado == self.Estado.APROBADA
            and self.tipo_accion == self.TipoAccion.EJECUTADA
            and not self.solicitante_es_delegado
            and self.nombre_solicitante.strip()
            and self.telefono_solicitante.strip()
        )

    def clean(self):
        super().clean()
        errores = {}
        hoy = timezone.localdate()
        if self.fecha_actividad:
            if self.fecha_actividad > hoy:
                errores["fecha_actividad"] = "No se puede registrar una actividad futura como realizada."
            inicio_semana = hoy - timedelta(days=hoy.weekday())
            # El lunes se admite corregir la semana anterior; desde el martes ya está cerrada.
            fecha_minima = inicio_semana - timedelta(days=7) if hoy.weekday() == 0 else inicio_semana
            if self.fecha_actividad < fecha_minima:
                errores["fecha_actividad"] = (
                    "El plazo de registro de esa semana ya terminó. "
                    "La semana anterior se cierra el lunes siguiente."
                )
        if self.funcionario_id and self.delegacion_id:
            if self.funcionario.delegacion_id != self.delegacion_id:
                errores["funcionario"] = "El funcionario no pertenece a esta delegación."
        if self.fecha_actividad and self.funcionario_id:
            mismos = type(self).objects.filter(
                funcionario_id=self.funcionario_id,
                fecha_actividad=self.fecha_actividad,
            )
            if self.pk:
                mismos = mismos.exclude(pk=self.pk)
            if mismos.count() >= 7:
                errores["fecha_actividad"] = (
                    "Este funcionario ya tiene 7 actividades registradas para ese día."
                )
        if self.periodo_id and self.fecha_actividad:
            if not self.periodo.fecha_inicio <= self.fecha_actividad <= self.periodo.fecha_fin:
                errores["periodo"] = "La fecha no pertenece al período de medición seleccionado."
        if errores:
            raise ValidationError(errores)

# EVA 3 - Gestión Operativa (modelos registrados en la aplicación gestion)
from .modelos_operativos_eva3 import AgendaCompromiso, MetaIndicador, ActividadRevision, ActividadIndicador

# Modelos de medición SGR, Evaluación 3
from .medicion_eva3_models import ConfiguracionMetaSGR, AusenciaSGR
