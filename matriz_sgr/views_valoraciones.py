"""Recepción delegada y validación documental por administración.

Deliberadamente NO altera el consolidado ni calcula bonificaciones/penalidades.
"""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from pathlib import PurePosixPath

from .forms_valoraciones import ValoracionCiudadanaForm, ResolverValoracionForm
from .modelos_valoraciones import ValoracionCiudadanaSGR, AuditoriaValoracionCiudadanaSGR


def _admin(u):
    return u.is_superuser or getattr(u,'rol','') == 'ADMIN'


def _delegacion_delegado(u):
    if getattr(u,'rol','') != 'DELEG' or u.is_superuser:
        return None
    try:
        return u.funcionario.delegacion
    except Exception:
        return None


def _listado_autorizado(u):
    qs = ValoracionCiudadanaSGR.objects.select_related('item','delegacion','periodo','funcionario','informado_por')
    if _admin(u):
        return qs
    delegacion = _delegacion_delegado(u)
    if delegacion is None:
        raise PermissionDenied('Solo delegados autorizados y administración pueden consultar estos documentos.')
    return qs.filter(delegacion=delegacion)


@login_required
@require_http_methods(['GET'])
def listado(request):
    qs = _listado_autorizado(request.user)
    estado = request.GET.get('estado','')
    if estado in ('PEN','VAL','REC'):
        qs = qs.filter(estado=estado)
    return render(request, 'matriz_sgr/valoraciones_listar.html', {
        'registros':qs[:120], 'estado_actual':estado,
        'puede_ingresar':_delegacion_delegado(request.user) is not None,
        'es_admin':_admin(request.user),
    })


@login_required
@require_http_methods(['GET','POST'])
def crear(request):
    delegacion = _delegacion_delegado(request.user)
    if delegacion is None:
        raise PermissionDenied('Solamente el Delegado de la delegación puede ingresar un documento formal.')
    form = ValoracionCiudadanaForm(request.POST or None, request.FILES or None, delegacion=delegacion)
    if request.method == 'POST' and form.is_valid():
        nuevo = form.save(commit=False)
        nuevo.delegacion = delegacion
        nuevo.informado_por = request.user
        nuevo.estado = ValoracionCiudadanaSGR.Estado.PENDIENTE
        try:
            nuevo.full_clean()
            with transaction.atomic():
                nuevo.save()
                AuditoriaValoracionCiudadanaSGR.objects.create(
                    valoracion=nuevo, usuario=request.user, accion='INGRESO',
                    detalle='Documento recibido por delegado, pendiente de revisión. Sin puntaje.')
        except ValidationError as exc:
            for campo, mensajes in exc.message_dict.items():
                campo = campo if campo in form.fields else None
                for msg in mensajes:
                    form.add_error(campo,msg)
        except IntegrityError:
            form.add_error('referencia','La referencia ya está registrada para esta delegación y período.')
        else:
            messages.success(request,'Documento ingresado para revisión, sin puntuación automática.')
            return redirect('matriz_sgr:valoracion_detalle',pk=nuevo.pk)
    return render(request,'matriz_sgr/valoraciones_crear.html',{'form':form,'delegacion':delegacion})


@login_required
@require_http_methods(['GET','POST'])
def detalle(request,pk):
    registro = get_object_or_404(_listado_autorizado(request.user),pk=pk)
    es_admin = _admin(request.user)
    if request.method == 'POST':
        if not es_admin:
            raise PermissionDenied('Solo administración puede validar o rechazar documentos.')
        form = ResolverValoracionForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                actual = ValoracionCiudadanaSGR.objects.select_for_update().get(pk=pk)
                if actual.estado != ValoracionCiudadanaSGR.Estado.PENDIENTE:
                    raise PermissionDenied('Este documento ya fue revisado y no puede cambiarse directamente.')
                actual.estado = form.cleaned_data['decision']
                actual.revisado_por = request.user
                actual.revisado_en = timezone.now()
                actual.observacion_revision = form.cleaned_data['observacion']
                try:
                    actual.full_clean()
                except ValidationError as exc:
                    form.add_error(None,'; '.join(exc.messages))
                else:
                    actual.save(update_fields=['estado','revisado_por','revisado_en','observacion_revision'])
                    AuditoriaValoracionCiudadanaSGR.objects.create(
                        valoracion=actual, usuario=request.user,
                        accion='VALIDACION' if actual.estado=='VAL' else 'RECHAZO',
                        detalle=actual.observacion_revision)
                    messages.success(request,'Revisión registrada. Sin impacto automático en indicadores.')
                    return redirect('matriz_sgr:valoracion_detalle',pk=pk)
    else:
        form = ResolverValoracionForm()
    return render(request,'matriz_sgr/valoraciones_detalle.html',{
        'registro':registro, 'form':form,
        'puede_revisar':es_admin and registro.estado=='PEN',
        'historial':registro.historial.select_related('usuario').all(),
    })


@login_required
@require_http_methods(['GET'])
def respaldo(request,pk):
    registro = get_object_or_404(_listado_autorizado(request.user),pk=pk)
    if not registro.respaldo:
        raise Http404('Documento no disponible.')
    return FileResponse(registro.respaldo.open('rb'), as_attachment=True,
        content_type='application/octet-stream',
        filename=PurePosixPath(registro.respaldo.name).name)
