"""Modelos incrementales para Gestión Operativa; no modifican tablas maestras."""
from decimal import Decimal
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models


class AgendaCompromiso(models.Model):
    class Estado(models.TextChoices):
        PLANIFICADO = "PLAN", "Planificado"
        EN_PROCESO = "PROC", "En proceso"
        REALIZADO = "REAL", "Realizado"
        CANCELADO = "CANC", "Cancelado"

    titulo = models.CharField(max_length=200)
    descripcion = models.TextField(blank=True)
    fecha = models.DateField()
    hora_inicio = models.TimeField(null=True, blank=True)
    hora_fin = models.TimeField(null=True, blank=True)
    delegacion = models.ForeignKey("delegaciones.Delegacion", on_delete=models.PROTECT, related_name="compromisos_eva3")
    responsable = models.ForeignKey("funcionarios.Funcionario", on_delete=models.PROTECT, related_name="compromisos_eva3")
    periodo = models.ForeignKey("gestion.Periodo", on_delete=models.SET_NULL, null=True, blank=True, related_name="compromisos_eva3")
    actividad = models.ForeignKey("gestion.Actividad", on_delete=models.SET_NULL, null=True, blank=True, related_name="compromisos_agenda")
    lugar = models.CharField(max_length=200, blank=True)
    estado = models.CharField(max_length=4, choices=Estado.choices, default=Estado.PLANIFICADO)
    observaciones = models.TextField(blank=True)
    creado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="compromisos_creados_eva3")
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["fecha", "hora_inicio", "pk"]
        verbose_name = "Compromiso de agenda"
        verbose_name_plural = "Compromisos de agenda"

    def __str__(self):
        return self.titulo

    @property
    def codigo(self):
        return f"SGR-AG-{self.pk:06d}" if self.pk else "PENDIENTE"

    def clean(self):
        super().clean()
        errores = {}
        if self.hora_inicio and self.hora_fin and self.hora_fin <= self.hora_inicio:
            errores["hora_fin"] = "La hora de término debe ser posterior a la de inicio."
        if self.responsable_id and self.delegacion_id and self.responsable.delegacion_id != self.delegacion_id:
            errores["responsable"] = "El responsable debe pertenecer a la delegación indicada."
        if self.periodo_id and self.fecha and not (self.periodo.fecha_inicio <= self.fecha <= self.periodo.fecha_fin):
            errores["periodo"] = "La fecha debe pertenecer al período seleccionado."
        if self.actividad_id:
            if self.delegacion_id and self.actividad.delegacion_id != self.delegacion_id:
                errores["actividad"] = "La actividad vinculada debe pertenecer a la misma delegación."
            if self.responsable_id and self.actividad.funcionario_id != self.responsable_id:
                errores["actividad"] = "La actividad vinculada debe tener el mismo responsable."
        if errores:
            raise ValidationError(errores)


class MetaIndicador(models.Model):
    """Meta básica por número de actividades válidas. No representa todas las fórmulas municipales."""
    nombre = models.CharField(max_length=160)
    delegacion = models.ForeignKey("delegaciones.Delegacion", on_delete=models.PROTECT, related_name="metas_eva3")
    periodo = models.ForeignKey("gestion.Periodo", on_delete=models.PROTECT, related_name="metas_eva3")
    meta_cantidad = models.PositiveIntegerField(validators=[MinValueValidator(1)], help_text="Cantidad de acciones aprobadas y elegibles")
    ponderacion = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("100.00"), validators=[MinValueValidator(Decimal("0.00")), MaxValueValidator(Decimal("100.00"))])
    activo = models.BooleanField(default=True)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["delegacion__nombre", "nombre"]
        verbose_name = "Meta de indicador"
        verbose_name_plural = "Metas de indicadores"
        constraints = [models.UniqueConstraint(fields=["nombre", "delegacion", "periodo"], name="uq_meta_eva3_deleg_period_nombre")]

    def __str__(self):
        return f"{self.nombre} / {self.delegacion}"


class ActividadRevision(models.Model):
    class Decision(models.TextChoices):
        APROBADA = "APR", "Aprobada"
        RECHAZADA = "RECH", "Rechazada"

    actividad = models.ForeignKey("gestion.Actividad", on_delete=models.PROTECT, related_name="revisiones_eva3")
    revisor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="revisiones_actividades_eva3")
    decision = models.CharField(max_length=4, choices=Decision.choices)
    observacion = models.TextField(blank=True)
    fecha = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-fecha", "-pk"]


class ActividadIndicador(models.Model):
    """Asociación explícita: una actividad validada cuenta para un solo ítem/meta."""
    actividad = models.OneToOneField("gestion.Actividad", on_delete=models.PROTECT, related_name="asignacion_meta_eva3")
    meta = models.ForeignKey("gestion.MetaIndicador", on_delete=models.PROTECT, related_name="asignaciones_eva3")
    asignado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="asignaciones_meta_eva3")
    asignado_en = models.DateTimeField(auto_now_add=True)

    def clean(self):
        super().clean()
        errores = {}
        if self.actividad_id and self.meta_id:
            if self.actividad.delegacion_id != self.meta.delegacion_id:
                errores["meta"] = "La meta debe ser de la misma delegación que la actividad."
            elif not (self.meta.periodo.fecha_inicio <= self.actividad.fecha_actividad <= self.meta.periodo.fecha_fin):
                errores["meta"] = "La actividad está fuera de las fechas de la meta."
        if errores:
            raise ValidationError(errores)
