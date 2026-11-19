from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class OrganizacionComunitaria(models.Model):
    """Catastro municipal; registros importados no se consideran verificados."""

    class Tipo(models.TextChoices):
        SIN_CLASIFICAR = 'SIN', 'Sin clasificar'
        JJVV = 'JJVV', 'Junta de vecinos'
        ADULTO_MAYOR = 'AM', 'Club o agrupación de adultos mayores'
        DEPORTIVA = 'DEP', 'Organización deportiva'
        CULTURAL = 'CUL', 'Organización cultural'
        JUVENIL = 'JUV', 'Organización juvenil'
        COMITE = 'COM', 'Comité comunitario'
        OTRA = 'OTRA', 'Otra organización'

    class Verificacion(models.TextChoices):
        PENDIENTE = 'PEND', 'Pendiente de verificación'
        VERIFICADA = 'VER', 'Verificada'
        OBSERVADA = 'OBS', 'Observada'

    nombre = models.CharField(max_length=255, db_index=True, verbose_name='Organización')
    tipo = models.CharField(max_length=5, choices=Tipo.choices, default=Tipo.SIN_CLASIFICAR)
    domicilio_legal = models.CharField(max_length=400, blank=True)
    territorio_origen = models.CharField(max_length=80, blank=True, help_text='Territorio tal como aparece en el Excel de origen')
    delegacion = models.ForeignKey('delegaciones.Delegacion', on_delete=models.PROTECT,
                                   related_name='organizaciones_comunitarias', null=True, blank=True)
    socios_activos = models.PositiveIntegerField(null=True, blank=True)
    fecha_constitucion = models.DateField(null=True, blank=True)
    numero_registro_pj = models.CharField(max_length=50, null=True, blank=True, unique=True,
                                          verbose_name='Número de registro P. J.')
    fecha_inscripcion = models.DateField(null=True, blank=True)
    registro_directorio = models.CharField(max_length=50, blank=True, verbose_name='Registro directorio Nº')
    estado_verificacion = models.CharField(max_length=4, choices=Verificacion.choices,
                                           default=Verificacion.PENDIENTE, db_index=True)
    observaciones = models.TextField(blank=True)
    fuente_archivo = models.CharField(max_length=255, blank=True)
    fila_origen = models.PositiveIntegerField(null=True, blank=True)
    creado_por = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                   on_delete=models.SET_NULL, related_name='organizaciones_creadas')
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['nombre', 'pk']
        verbose_name = 'Organización comunitaria'
        verbose_name_plural = 'Organizaciones comunitarias'

    def __str__(self):
        return self.nombre

    def clean(self):
        super().clean()
        if not self.nombre or not self.nombre.strip():
            raise ValidationError({'nombre': 'Ingresa el nombre de la organización.'})
        if self.numero_registro_pj is not None:
            self.numero_registro_pj = self.numero_registro_pj.strip() or None

    @property
    def codigo(self):
        return f'SGR-ORG-{self.pk:06d}' if self.pk else 'PENDIENTE'
