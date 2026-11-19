"""Felicitaciones y reclamos formales: trazabilidad SIN puntuación automática.

La matriz importa bonificaciones y penalizaciones como referencias, pero el
procedimiento municipal no fija una tasa por cada documento. Por ello ninguna
valoración impacta el consolidado sin una regla posterior autorizada.
"""
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator
from django.db import models
from django.utils import timezone


class ValoracionCiudadanaSGR(models.Model):
    class Medio(models.TextChoices):
        AL_DELEGADO = 'DELEG', 'Dirigida al delegado'
        EN_DELEGACION = 'SEDE', 'Presentada formalmente en la delegación'
        AL_FUNCIONARIO = 'FUNC', 'Mensaje directo al funcionario'

    class Estado(models.TextChoices):
        PENDIENTE = 'PEN', 'Pendiente de revisión'
        VALIDADA = 'VAL', 'Validada documentalmente'
        RECHAZADA = 'REC', 'Rechazada'

    item = models.ForeignKey('matriz_sgr.ItemMatrizSGR', on_delete=models.PROTECT,
                             related_name='valoraciones_ciudadanas')
    delegacion = models.ForeignKey('delegaciones.Delegacion', on_delete=models.PROTECT)
    periodo = models.ForeignKey('gestion.Periodo', on_delete=models.PROTECT)
    funcionario = models.ForeignKey('funcionarios.Funcionario', on_delete=models.PROTECT,
                                    blank=True, null=True,
                                    help_text='Opcional: destinatario individual; vacío para registro colectivo.')
    fecha_documento = models.DateField()
    referencia = models.CharField(max_length=80, verbose_name='Número de oficio o referencia')
    remitente = models.CharField(max_length=160, verbose_name='Nombre del remitente')
    medio = models.CharField(max_length=5, choices=Medio.choices)
    descripcion = models.TextField(verbose_name='Detalle del documento')
    respaldo = models.FileField(upload_to='matriz_sgr/valoraciones/%Y/%m/',
        validators=[FileExtensionValidator(allowed_extensions=['pdf','jpg','jpeg','png','docx'])],
        help_text='Documento formal, máximo 5 MB; almacenamiento privado.')
    estado = models.CharField(max_length=3, choices=Estado.choices,
                               default=Estado.PENDIENTE)
    informado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                                       related_name='valoraciones_informadas')
    revisado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                                    related_name='valoraciones_revisadas', null=True, blank=True)
    observacion_revision = models.TextField(blank=True)
    registrado_en = models.DateTimeField(default=timezone.now, editable=False)
    revisado_en = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-registrado_en','-pk']
        constraints = [models.UniqueConstraint(fields=['delegacion','periodo','referencia'],
                            name='uq_valoracion_ref_deleg_periodo')]
        verbose_name = 'Valoración ciudadana formal'
        verbose_name_plural = 'Valoraciones ciudadanas formales'

    def __str__(self):
        return f'{self.item.nombre} · {self.referencia}'

    @property
    def es_felicitacion(self):
        return self.item_id and self.item.nombre.upper().strip().startswith('FELICITACIONES')

    def clean(self):
        super().clean()
        errores = {}
        if self.item_id:
            nombre = self.item.nombre.upper().strip()
            if self.item.clase != 'ESP' or not (nombre.startswith('FELICITACIONES') or nombre.startswith('RECLAMOS')):
                errores['item'] = 'Seleccione una felicitación o reclamo formal de la matriz.'
            if nombre.startswith('FELICITACIONES') and self.medio == self.Medio.AL_FUNCIONARIO:
                errores['medio'] = 'Una felicitación enviada directamente al gestor no es elegible.'
        if self.funcionario_id and self.delegacion_id and self.funcionario.delegacion_id != self.delegacion_id:
            errores['funcionario'] = 'El funcionario debe pertenecer a la misma delegación.'
        if self.periodo_id and self.fecha_documento:
            if not (self.periodo.fecha_inicio <= self.fecha_documento <= self.periodo.fecha_fin):
                errores['fecha_documento'] = 'La fecha debe pertenecer al período seleccionado.'
        if self.informado_por_id and (self.informado_por.rol != 'DELEG' or self.informado_por.is_superuser):
            errores['informado_por'] = 'El ingreso formal debe efectuarlo una cuenta de Delegado.'
        if self.informado_por_id and self.delegacion_id:
            try:
                perfil = self.informado_por.funcionario
            except Exception:
                perfil = None
            if perfil is None or perfil.delegacion_id != self.delegacion_id:
                errores['informado_por'] = 'El delegado debe estar asociado a esta delegación.'
        if not self.respaldo:
            errores['respaldo'] = 'Adjunte un documento formal de respaldo.'
        elif getattr(self.respaldo, 'size', 0) > 5 * 1024 * 1024:
            errores['respaldo'] = 'El respaldo no debe superar 5 MB.'
        if len((self.descripcion or '').strip()) < 20:
            errores['descripcion'] = 'Describa el antecedente formal (mínimo 20 caracteres).'
        if self.estado != self.Estado.PENDIENTE:
            if not self.revisado_por_id or not self.revisado_en or len(self.observacion_revision.strip()) < 15:
                errores['estado'] = 'La revisión requiere responsable, fecha y fundamento (15 caracteres).'
        if errores:
            raise ValidationError(errores)


class AuditoriaValoracionCiudadanaSGR(models.Model):
    valoracion = models.ForeignKey('matriz_sgr.ValoracionCiudadanaSGR',
                                   on_delete=models.PROTECT, related_name='historial')
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    accion = models.CharField(max_length=16)
    detalle = models.TextField()
    fecha = models.DateTimeField(default=timezone.now, editable=False)

    class Meta:
        ordering = ['-fecha', '-pk']
        verbose_name = 'Auditoría de valoración ciudadana'
