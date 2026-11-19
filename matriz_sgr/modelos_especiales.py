"""Mediciones municipales que NO equivalen a conteos de actividades aprobadas.

Se guardan aparte de MetaIndicador: no altera el motor de cálculo ya probado.
Los casos FELICITACIONES/RECLAMOS nunca generan puntuación automática aquí.
"""
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, FileExtensionValidator
from django.db import models
from django.utils import timezone


class MedicionEspecialSGR(models.Model):
    class Estado(models.TextChoices):
        BORRADOR = 'BOR', 'Borrador'
        VALIDADA = 'VAL', 'Validada'

    item = models.ForeignKey('matriz_sgr.ItemMatrizSGR', on_delete=models.PROTECT,
                             related_name='mediciones_especiales')
    delegacion = models.ForeignKey('delegaciones.Delegacion', on_delete=models.PROTECT)
    periodo = models.ForeignKey('gestion.Periodo', on_delete=models.PROTECT)
    # Solo para PORC: numerador / denominador, ambos en unidades del mismo período.
    resueltos = models.PositiveIntegerField(null=True, blank=True,
                 verbose_name='Casos resueltos')
    recibidos = models.PositiveIntegerField(null=True, blank=True,
                 verbose_name='Casos ingresados al tubo')
    # Solo para DIN: objetivo fijado expresamente por la autoridad para este período.
    objetivo_variable = models.DecimalField(max_digits=12, decimal_places=3,
                 null=True, blank=True, validators=[MinValueValidator(Decimal('0.001'))])
    realizado_variable = models.DecimalField(max_digits=12, decimal_places=3,
                 null=True, blank=True, validators=[MinValueValidator(Decimal('0'))])
    unidad_variable = models.CharField(max_length=80, blank=True)
    fuente = models.TextField(blank=True, verbose_name='Justificación y fuente de los datos')
    respaldo = models.FileField(upload_to='matriz_sgr/mediciones/%Y/%m/', blank=True,
                validators=[FileExtensionValidator(allowed_extensions=['pdf', 'jpg', 'jpeg', 'png', 'docx', 'xlsx'])])
    estado = models.CharField(max_length=3, choices=Estado.choices, default=Estado.BORRADOR)
    registrado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                  related_name='mediciones_especiales_registradas')
    validado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                  related_name='mediciones_especiales_validadas', null=True, blank=True)
    validado_en = models.DateTimeField(null=True, blank=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['item__hoja', 'item__fila', 'delegacion_id']
        constraints = [models.UniqueConstraint(fields=['item','delegacion','periodo'],
                       name='uq_med_especial_item_deleg_per')]
        verbose_name = 'Medición especial SGR'

    def __str__(self):
        return f'{self.item.nombre} — {self.delegacion} ({self.periodo})'

    def clean(self):
        super().clean()
        errores = {}
        if not self.item_id:
            errores['item'] = 'Se requiere un ítem de matriz.'
        elif self.item.clase not in ('PORC', 'DIN'):
            errores['item'] = 'Este ítem no admite medición especial automática.'
        elif not self.item.ponderacion or self.item.ponderacion <= 0 or self.item.ponderacion > 100:
            errores['item'] = 'La ponderación de origen necesita revisión.'
        elif self.item.clase == 'PORC':
            if self.item.meta_original is None or not (Decimal('0') < self.item.meta_original <= Decimal('1')):
                errores['item'] = 'El objetivo porcentual del Excel no es válido.'
            if self.resueltos is not None and self.recibidos is not None and self.resueltos > self.recibidos:
                errores['resueltos'] = 'Los casos resueltos no pueden superar a los recibidos.'
            if self.estado == self.Estado.VALIDADA and (self.recibidos is None or self.recibidos == 0 or self.resueltos is None):
                errores['recibidos'] = 'Indica recibidos (mayor que 0) y resueltos antes de validar.'
        elif self.item.clase == 'DIN':
            if self.estado == self.Estado.VALIDADA and (self.objetivo_variable is None or self.objetivo_variable <= 0):
                errores['objetivo_variable'] = 'Define un objetivo oficial positivo para este período.'
            if self.estado == self.Estado.VALIDADA and (self.realizado_variable is None or self.realizado_variable < 0):
                errores['realizado_variable'] = 'Indica el resultado observado.'
        if self.estado == self.Estado.VALIDADA:
            if len(self.fuente.strip()) < 15:
                errores['fuente'] = 'Antes de validar, documenta la fuente y el criterio (mínimo 15 caracteres).'
            if not self.validado_por_id or not self.validado_en:
                errores['estado'] = 'La validación debe indicar responsable y fecha.'
        if errores:
            raise ValidationError(errores)


class AuditoriaMedicionEspecialSGR(models.Model):
    medicion = models.ForeignKey('matriz_sgr.MedicionEspecialSGR', on_delete=models.PROTECT,
                    related_name='historial')
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    accion = models.CharField(max_length=15)
    descripcion = models.TextField()
    fecha = models.DateTimeField(default=timezone.now, editable=False)

    class Meta:
        ordering = ['-fecha','-pk']
        verbose_name = 'Registro de auditoría de medición'
