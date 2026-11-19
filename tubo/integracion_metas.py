"""Vincula una gestión social aprobada a UNA actividad, sin otro motor de puntaje.

- Reutiliza ActividadIndicador y calcular_resumen_meta.
- Puede asociar una actividad aprobada preexistente O registrar una acción nueva.
- Requiere validación humana sobre que la acción fue ejecutada, no coordinada.
- Nunca modifica ni puntúa automáticamente una gestión solo por aprobarla.
"""
from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from funcionarios.models import Funcionario
from gestion.medicion_eva3_calculos import meta_aplica_a_actividad
from gestion.models import Actividad, ActividadIndicador, ActividadRevision, MetaIndicador
from .models import GestionSocial, HistorialGestion, VinculoGestionActividad
from .permisos import es_admin, delegacion_usuario, visibles


def puede_vincular_meta(usuario, gestion):
    if not usuario.is_authenticated or gestion.estado != GestionSocial.Estado.APROBADA:
        return False
    if es_admin(usuario):
        return True
    return (getattr(usuario, 'rol', '') in ('COORD', 'DELEG', 'VERIF')
            and delegacion_usuario(usuario) == gestion.delegacion_id)


def _mismo_solicitante(actividad, gestion):
    """Evita vincular una actividad de otro vecino por coincidencia de funcionario."""
    import re
    nombre_a = ' '.join((actividad.nombre_solicitante or '').casefold().split())
    nombre_g = ' '.join((gestion.vecino.nombre or '').casefold().split())
    telefono_a = re.sub(r'\D', '', actividad.telefono_solicitante or '')
    telefono_g = re.sub(r'\D', '', gestion.vecino.telefono or '')
    return bool(nombre_a and telefono_a and nombre_a == nombre_g and telefono_a == telefono_g)


def _gestion_puntuable(gestion):
    return bool(gestion.estado == GestionSocial.Estado.APROBADA
                and not gestion.solicitante_es_delegado
                and gestion.vecino.nombre.strip()
                and gestion.vecino.telefono.strip())


class VincularMetaForm(forms.Form):
    MODO = [('existente', 'Vincular una actividad aprobada existente'),
            ('nueva', 'Registrar una acción ejecutada (no registrada previamente)')]
    modo = forms.ChoiceField(label='Forma de vinculación', choices=MODO,
                             widget=forms.RadioSelect, initial='existente')
    meta = forms.ModelChoiceField(label='Meta a la que aportará la gestión',
                                   queryset=MetaIndicador.objects.none())
    actividad_existente = forms.ModelChoiceField(
        label='Actividad aprobada existente', required=False,
        queryset=Actividad.objects.none(),
        help_text='Seleccione una actividad que ya haya sido aprobada en Gestión Operativa.')
    fecha_actividad = forms.DateField(
        label='Fecha real de ejecución', required=False,
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}))
    accion_realizada = forms.CharField(
        label='Acción efectivamente realizada', required=False, max_length=2500,
        widget=forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
        help_text='No contabilice reuniones preparatorias ni solicitudes sin solución ejecutada.')
    confirmacion = forms.BooleanField(
        label='Confirmo que esta acción NO está registrada previamente en Actividades',
        required=False)

    def __init__(self, *args, gestion, **kwargs):
        self.gestion = gestion
        super().__init__(*args, **kwargs)
        self.fields['meta'].queryset = MetaIndicador.objects.filter(
            delegacion_id=gestion.delegacion_id, activo=True,
        ).select_related('periodo').order_by('nombre')
        # No mostrar actividades ya vinculadas a otra gestión.
        self.fields['actividad_existente'].queryset = Actividad.objects.filter(
            delegacion_id=gestion.delegacion_id,
            funcionario_id=gestion.responsable_id,
            estado=Actividad.Estado.APROBADA,
        ).exclude(origen_tubo__isnull=False).select_related('periodo')
        self.fields['fecha_actividad'].initial = timezone.localdate()
        for clave in ('meta', 'actividad_existente'):
            self.fields[clave].widget.attrs['class'] = 'form-select'

    def clean(self):
        datos = super().clean()
        if not _gestion_puntuable(self.gestion):
            raise forms.ValidationError(
                'La gestión no puede puntuar: debe estar aprobada, tener nombre y teléfono, '
                'y el solicitante no puede ser el delegado.')
        modo, meta = datos.get('modo'), datos.get('meta')
        if not meta:
            return datos
        if modo == 'existente':
            actividad = datos.get('actividad_existente')
            if not actividad:
                self.add_error('actividad_existente', 'Seleccione una actividad aprobada.')
            elif not actividad.elegible_para_puntaje:
                self.add_error('actividad_existente', 'La actividad no cumple las reglas de puntuación.')
            elif not _mismo_solicitante(actividad, self.gestion):
                self.add_error('actividad_existente', 'El nombre y teléfono de la actividad deben coincidir con el vecino de la gestión.')
            elif not meta_aplica_a_actividad(meta, actividad):
                self.add_error('meta', 'La meta no corresponde a la actividad, funcionario o período.')
            elif ActividadIndicador.objects.filter(actividad=actividad).exclude(meta=meta).exists():
                self.add_error('actividad_existente', 'Esta actividad ya aporta a otra meta.')
        elif modo == 'nueva':
            fecha = datos.get('fecha_actividad')
            accion = (datos.get('accion_realizada') or '').strip()
            if not fecha:
                self.add_error('fecha_actividad', 'Indique la fecha en que se ejecutó la acción.')
            elif not (meta.periodo.fecha_inicio <= fecha <= meta.periodo.fecha_fin):
                self.add_error('fecha_actividad', 'La fecha no corresponde al trimestre de la meta.')
            if len(accion) < 12:
                self.add_error('accion_realizada', 'Describa una acción efectivamente terminada (mínimo 12 caracteres).')
            if not datos.get('confirmacion'):
                self.add_error('confirmacion', 'Debe confirmar que la acción no está registrada previamente.')
        return datos


def _vincular_validado(gestion_id, datos, usuario):
    """Todo o nada: bloqueo, comprobaciones, actividad, meta, vínculo e historial."""
    with transaction.atomic():
        gestion = get_object_or_404(
            GestionSocial.objects.select_for_update().select_related('vecino', 'responsable'), pk=gestion_id)
        if not puede_vincular_meta(usuario, gestion):
            raise PermissionDenied('No tiene permiso para vincular esta gestión.')
        if not _gestion_puntuable(gestion):
            raise ValidationError('La gestión no reúne las condiciones municipales para puntuar.')
        if VinculoGestionActividad.objects.filter(gestion=gestion).exists():
            raise ValidationError('Esta gestión ya está vinculada a una actividad.')
        meta = MetaIndicador.objects.select_related('periodo').get(pk=datos['meta'].pk)
        if not meta.activo or meta.delegacion_id != gestion.delegacion_id:
            raise ValidationError('La meta no está activa o pertenece a otra delegación.')
        if datos['modo'] == 'existente':
            actividad = Actividad.objects.select_for_update().get(pk=datos['actividad_existente'].pk)
            if actividad.delegacion_id != gestion.delegacion_id or actividad.funcionario_id != gestion.responsable_id:
                raise ValidationError('La actividad debe pertenecer a la misma delegación y responsable.')
            if actividad.estado != Actividad.Estado.APROBADA or not actividad.elegible_para_puntaje:
                raise ValidationError('La actividad no está aprobada o no es elegible para puntaje.')
            if VinculoGestionActividad.objects.filter(actividad=actividad).exists():
                raise ValidationError('Esta actividad ya está vinculada a otra gestión.')
            if not _mismo_solicitante(actividad, gestion):
                raise ValidationError('La actividad no corresponde al mismo vecino (nombre y teléfono).')
        else:
            # Serializar la creación por funcionario para hacer cumplir el máximo 7/día.
            Funcionario.objects.select_for_update().get(pk=gestion.responsable_id)
            actividad = Actividad(
                fecha_actividad=datos['fecha_actividad'], delegacion=gestion.delegacion,
                funcionario=gestion.responsable, periodo=meta.periodo,
                tipo_accion=Actividad.TipoAccion.EJECUTADA,
                titulo=gestion.titulo, descripcion=gestion.descripcion,
                accion_realizada=datos['accion_realizada'].strip(),
                nombre_solicitante=gestion.vecino.nombre.strip()[:150],
                telefono_solicitante=gestion.vecino.telefono.strip()[:25],
                solicitante_es_delegado=gestion.solicitante_es_delegado,
                estado=Actividad.Estado.APROBADA,
                creado_por=gestion.creado_por,
            )
            # Incluye la regla del cierre semanal, fecha futura, tope diario y período.
            actividad.full_clean()
            actividad.save()
            ActividadRevision.objects.create(
                actividad=actividad, revisor=usuario,
                decision=ActividadRevision.Decision.APROBADA,
                observacion='Acción aprobada desde gestión social ' + gestion.codigo,
            )
        if not meta_aplica_a_actividad(meta, actividad):
            raise ValidationError('La meta no corresponde al funcionario, cargo o trimestre de la actividad.')
        asignacion, creada = ActividadIndicador.objects.get_or_create(
            actividad=actividad, defaults={'meta': meta, 'asignado_por': usuario})
        if not creada and asignacion.meta_id != meta.pk:
            raise ValidationError('La actividad ya aporta a otra meta.')
        if creada:
            asignacion.full_clean()
        enlace = VinculoGestionActividad(gestion=gestion, actividad=actividad, vinculado_por=usuario)
        enlace.full_clean()
        enlace.save()
        HistorialGestion.objects.create(
            gestion=gestion, usuario=usuario, accion='VINCULACION_META',
            descripcion=f'Vinculada con {actividad.codigo} y meta «{meta.nombre}» (sin doble conteo).',
        )
        return actividad


@login_required
@require_http_methods(['GET', 'POST'])
def vincular_meta(request, pk):
    gestion = get_object_or_404(
        visibles(GestionSocial, request.user).select_related('delegacion', 'vecino', 'responsable'), pk=pk)
    if not puede_vincular_meta(request.user, gestion):
        raise PermissionDenied('Solo una jefatura o revisor autorizado puede vincular una gestión aprobada.')
    if VinculoGestionActividad.objects.filter(gestion=gestion).exists():
        messages.info(request, 'La gestión ya tiene una actividad vinculada.')
        return redirect('tubo:detalle_gestion', pk=pk)
    formulario = VincularMetaForm(request.POST or None, gestion=gestion)
    if request.method == 'POST' and formulario.is_valid():
        try:
            actividad = _vincular_validado(gestion.pk, formulario.cleaned_data, request.user)
        except (ValidationError, IntegrityError) as exc:
            formulario.add_error(None, 'No se pudo vincular: ' +
                                 ('; '.join(exc.messages) if isinstance(exc, ValidationError) else 'conflicto de datos. Vuelva a cargar el formulario.'))
        else:
            messages.success(request, f'Gestión vinculada correctamente a {actividad.codigo}. El indicador se recalcula con la actividad aprobada.')
            return redirect('tubo:detalle_gestion', pk=pk)
    return render(request, 'tubo/vincular_meta.html', {'gestion': gestion, 'formulario': formulario})
