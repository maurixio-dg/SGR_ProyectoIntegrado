"""Solicitudes/gestiones y cartas; independiente de Actividad y de su motor de puntuación."""
from pathlib import Path
import re

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator
from django.db import models
from django.utils import timezone


def validar_documento(archivo):
    if archivo and archivo.size > 5 * 1024 * 1024:
        raise ValidationError('El archivo no puede superar 5 MB.')
    if archivo and Path(archivo.name).suffix.lower() not in {'.pdf', '.jpg', '.jpeg', '.png', '.docx', '.xlsx'}:
        raise ValidationError('Archivo no permitido. Use PDF, imagen, Word o Excel.')


def normalizar_rut(valor):
    valor = re.sub(r'[^0-9kK]', '', valor or '').upper()
    if len(valor) < 2 or len(valor) > 9:
        raise ValidationError('Ingrese un RUT chileno válido.')
    cuerpo, dv = valor[:-1], valor[-1]
    if not cuerpo.isdigit():
        raise ValidationError('Ingrese un RUT chileno válido.')
    suma = sum(int(d) * (2 + (i % 6)) for i, d in enumerate(reversed(cuerpo)))
    calculado = str(11 - suma % 11)
    if calculado == '11':
        calculado = '0'
    elif calculado == '10':
        calculado = 'K'
    if calculado != dv:
        raise ValidationError('El dígito verificador del RUT no es válido.')
    return f'{int(cuerpo)}-{dv}'


class Territorio(models.Model):
    delegacion = models.ForeignKey('delegaciones.Delegacion', on_delete=models.PROTECT, related_name='territorios_tubo')
    nombre = models.CharField(max_length=120)
    descripcion = models.TextField(blank=True)
    activo = models.BooleanField(default=True)

    class Meta:
        ordering = ['delegacion__nombre', 'nombre']
        constraints = [models.UniqueConstraint(fields=['delegacion', 'nombre'], name='uq_territorio_delegacion_nombre')]

    def __str__(self):
        return f'{self.nombre} · {self.delegacion}'


class Vecino(models.Model):
    rut = models.CharField(max_length=12, unique=True, db_index=True)
    nombre = models.CharField(max_length=160, db_index=True)
    telefono = models.CharField(max_length=30, blank=True)
    email = models.EmailField(blank=True)
    direccion = models.CharField(max_length=250, blank=True)
    delegacion = models.ForeignKey('delegaciones.Delegacion', on_delete=models.PROTECT, related_name='vecinos_tubo')
    territorio = models.ForeignKey('tubo.Territorio', on_delete=models.SET_NULL, blank=True, null=True)
    organizacion = models.ForeignKey('organizaciones.OrganizacionComunitaria', on_delete=models.SET_NULL, blank=True, null=True)
    creado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='vecinos_tubo_creados')
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['nombre']

    def __str__(self):
        return f'{self.nombre} ({self.rut})'

    def clean(self):
        super().clean()
        errores = {}
        try:
            self.rut = normalizar_rut(self.rut)
        except ValidationError as exc:
            errores['rut'] = exc.messages
        if self.territorio_id and self.delegacion_id and self.territorio.delegacion_id != self.delegacion_id:
            errores['territorio'] = 'El territorio debe pertenecer a la delegación.'
        if self.organizacion_id and self.organizacion.delegacion_id and self.delegacion_id != self.organizacion.delegacion_id:
            errores['organizacion'] = 'La organización está asociada a otra delegación.'
        if errores:
            raise ValidationError(errores)


class TipoAtencion(models.Model):
    nombre = models.CharField(max_length=120, unique=True)
    activo = models.BooleanField(default=True)
    def __str__(self):
        return self.nombre
    class Meta:
        ordering = ['nombre']


class SubtipoAtencion(models.Model):
    tipo = models.ForeignKey('tubo.TipoAtencion', on_delete=models.PROTECT, related_name='subtipos')
    nombre = models.CharField(max_length=120)
    activo = models.BooleanField(default=True)

    class Meta:
        ordering = ['tipo__nombre','nombre']
        constraints = [models.UniqueConstraint(fields=['tipo','nombre'], name='uq_tubo_subtipo_tipo_nombre')]

    def __str__(self):
        return f'{self.tipo} / {self.nombre}'


class GestionSocial(models.Model):
    class Estado(models.TextChoices):
        PENDIENTE = 'PEND', 'Pendiente'
        EN_PROCESO = 'PROC', 'En proceso'
        MAS_ANTECEDENTES = 'MAS', 'Más antecedentes'
        APROBADA = 'APR', 'Aprobada'
        RECHAZADA = 'RECH', 'Rechazada'

    delegacion = models.ForeignKey('delegaciones.Delegacion', on_delete=models.PROTECT, related_name='gestiones_tubo')
    territorio = models.ForeignKey('tubo.Territorio', on_delete=models.SET_NULL, null=True, blank=True)
    vecino = models.ForeignKey('tubo.Vecino', on_delete=models.PROTECT, related_name='gestiones_tubo')
    tipo = models.ForeignKey('tubo.TipoAtencion', on_delete=models.PROTECT)
    subtipo = models.ForeignKey('tubo.SubtipoAtencion', on_delete=models.PROTECT, null=True, blank=True)
    responsable = models.ForeignKey('funcionarios.Funcionario', on_delete=models.PROTECT, related_name='gestiones_responsable_tubo')
    titulo = models.CharField(max_length=200)
    descripcion = models.TextField()
    ingresa_tubo = models.BooleanField(default=True, verbose_name='Ingresar al Tubo de seguimiento')
    solicitante_es_delegado = models.BooleanField(default=False)
    estado = models.CharField(max_length=4, choices=Estado.choices, default=Estado.PENDIENTE, db_index=True)
    evidencia = models.FileField(upload_to='tubo/gestiones/%Y/%m/', blank=True,
        validators=[FileExtensionValidator(['pdf', 'jpg','jpeg','png','docx','xlsx']), validar_documento])
    creado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='gestiones_sociales_creadas')
    fecha_registro = models.DateTimeField(default=timezone.now, editable=False, db_index=True)
    fecha_revision = models.DateTimeField(null=True, blank=True)
    revisado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name='gestiones_sociales_revisadas')
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-fecha_registro', '-pk']
        indexes = [models.Index(fields=['delegacion','estado'], name='tubo_deleg_estado_idx')]

    @property
    def codigo(self):
        return f'SGR-TUB-{self.pk:06d}' if self.pk else 'PENDIENTE'

    def __str__(self):
        return f'{self.codigo} · {self.titulo}'

    def clean(self):
        super().clean()
        errores = {}
        if self.delegacion_id and self.vecino_id and self.vecino.delegacion_id != self.delegacion_id:
            errores['vecino'] = 'El vecino debe pertenecer a la delegación.'
        if self.delegacion_id and self.responsable_id and self.responsable.delegacion_id != self.delegacion_id:
            errores['responsable'] = 'El responsable debe pertenecer a la delegación.'
        if self.delegacion_id and self.territorio_id and self.territorio.delegacion_id != self.delegacion_id:
            errores['territorio'] = 'El territorio debe pertenecer a la delegación.'
        if self.tipo_id and not self.tipo.activo:
            errores['tipo'] = 'Seleccione un tipo de atención activo.'
        if self.subtipo_id and self.tipo_id and self.subtipo.tipo_id != self.tipo_id:
            errores['subtipo'] = 'El subtipo no corresponde al tipo elegido.'
        if self.subtipo_id and not self.subtipo.activo:
            errores['subtipo'] = 'Seleccione un subtipo activo.'
        if errores:
            raise ValidationError(errores)


class HitoGestion(models.Model):
    gestion = models.ForeignKey('tubo.GestionSocial', on_delete=models.PROTECT, related_name='hitos')
    descripcion = models.TextField()
    creado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-creado_en', '-pk']


class HistorialGestion(models.Model):
    gestion = models.ForeignKey('tubo.GestionSocial', on_delete=models.PROTECT, related_name='historial')
    accion = models.CharField(max_length=30)
    descripcion = models.TextField(blank=True)
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    creado_en = models.DateTimeField(auto_now_add=True)
    class Meta:
        ordering = ['-creado_en', '-pk']


class CartaTubo(models.Model):
    class Estado(models.TextChoices):
        BORRADOR = 'BOR', 'Borrador'
        ENVIADA = 'ENV', 'Enviada'
        RECIBIDA = 'REC', 'Recibida'
        CERRADA = 'CER', 'Cerrada'

    delegacion = models.ForeignKey('delegaciones.Delegacion', on_delete=models.PROTECT, related_name='cartas_tubo')
    gestion = models.ForeignKey('tubo.GestionSocial', on_delete=models.PROTECT, null=True, blank=True, related_name='cartas')
    asunto = models.CharField(max_length=200)
    destinatario = models.CharField(max_length=160)
    numero_oficio = models.CharField(max_length=60, blank=True)
    descripcion = models.TextField(blank=True)
    estado = models.CharField(max_length=3, choices=Estado.choices, default=Estado.BORRADOR, db_index=True)
    adjunto = models.FileField(upload_to='tubo/cartas/%Y/%m/', blank=True,
        validators=[FileExtensionValidator(['pdf','jpg','jpeg','png','docx','xlsx']), validar_documento])
    creado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='cartas_tubo_creadas')
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-creado_en','-pk']

    @property
    def codigo(self):
        return f'SGR-CAR-{self.pk:06d}' if self.pk else 'PENDIENTE'

    def __str__(self):
        return f'{self.codigo} · {self.asunto}'

    def clean(self):
        super().clean()
        if self.gestion_id and self.delegacion_id and self.gestion.delegacion_id != self.delegacion_id:
            raise ValidationError({'gestion':'La gestión debe pertenecer a la misma delegación.'})


class VinculoGestionActividad(models.Model):
    """Cada gestión enlaza a UNA actividad, cada actividad proviene de UNA gestión como máximo."""
    gestion = models.OneToOneField('tubo.GestionSocial', on_delete=models.PROTECT,
                                   related_name='vinculo_actividad')
    actividad = models.OneToOneField('gestion.Actividad', on_delete=models.PROTECT,
                                     related_name='origen_tubo')
    vinculado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                                      related_name='vinculaciones_tubo')
    vinculado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Vínculo de gestión social con actividad'
        verbose_name_plural = 'Vínculos de gestiones sociales con actividades'

    def __str__(self):
        return f'{self.gestion.codigo} → {self.actividad.codigo}'
