"""Interfaz administrativa para medir ítems porcentuales y variables sin alterar Actividades."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from .calculos_especiales import calcular_especial
from .forms_especiales import CrearMedicionEspecialForm, EditarMedicionEspecialForm
from .models import ItemMatrizSGR, MedicionEspecialSGR, AuditoriaMedicionEspecialSGR


def _exigir_admin(user):
    if not (user.is_superuser or getattr(user, 'rol', '') == 'ADMIN'):
        raise PermissionDenied('Solo administración puede gestionar mediciones especiales.')


@login_required
@require_http_methods(['GET'])
def listado(request):
    _exigir_admin(request.user)
    clase = request.GET.get('clase', '')
    items = ItemMatrizSGR.objects.select_related('catalogo').filter(clase__in=['PORC','DIN','ESP'])
    if clase in ('PORC','DIN','ESP'):
        items = items.filter(clase=clase)
    mediciones = (MedicionEspecialSGR.objects.select_related('item','delegacion','periodo')
                  .order_by('-actualizado_en')[:150])
    resultados = [calcular_especial(m) for m in mediciones]
    return render(request, 'matriz_sgr/especiales_listar.html', {
        'items': items.order_by('-catalogo_id','hoja','fila')[:200],
        'resultados': resultados, 'clase_actual': clase,
    })


@login_required
@require_http_methods(['GET', 'POST'])
def crear(request, pk):
    _exigir_admin(request.user)
    item = get_object_or_404(ItemMatrizSGR.objects.select_related('catalogo'), pk=pk)
    if item.clase not in ('PORC','DIN'):
        messages.error(request, 'Este ítem requiere una regla municipal específica antes de generar puntuación.')
        return redirect('matriz_sgr:detalle', pk=item.catalogo_id)
    if not item.ponderacion or item.ponderacion <= 0 or item.ponderacion > 100:
        messages.error(request, 'No se puede medir un ítem sin ponderación válida.')
        return redirect('matriz_sgr:detalle', pk=item.catalogo_id)
    form = CrearMedicionEspecialForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        delegacion = form.cleaned_data['delegacion']
        periodo = form.cleaned_data['periodo']
        existente = MedicionEspecialSGR.objects.filter(item=item, delegacion=delegacion, periodo=periodo).first()
        if existente:
            messages.info(request, 'Ya existe una medición para ese ítem, delegación y período.')
            return redirect('matriz_sgr:especial_editar', pk=existente.pk)
        try:
            with transaction.atomic():
                medicion = MedicionEspecialSGR(
                    item=item, delegacion=delegacion, periodo=periodo,
                    registrado_por=request.user,
                )
                medicion.full_clean()
                medicion.save()
                AuditoriaMedicionEspecialSGR.objects.create(
                    medicion=medicion, usuario=request.user, accion='CREACION',
                    descripcion='Se creó una medición en borrador sin puntuación.',
                )
        except (ValidationError, IntegrityError):
            form.add_error(None, 'No fue posible crear la medición; comprueba que no exista otra igual.')
        else:
            return redirect('matriz_sgr:especial_editar', pk=medicion.pk)
    return render(request, 'matriz_sgr/especiales_crear.html', {'item': item, 'form': form})


@login_required
@require_http_methods(['GET','POST'])
def editar(request, pk):
    _exigir_admin(request.user)
    medicion = get_object_or_404(
        MedicionEspecialSGR.objects.select_related('item','delegacion','periodo'), pk=pk)
    if medicion.estado == MedicionEspecialSGR.Estado.VALIDADA:
        if request.method == 'POST':
            raise PermissionDenied('La medición validada es inmutable; cualquier corrección requiere un procedimiento auditado.')
        return render(request, 'matriz_sgr/especiales_editar.html', {
            'medicion':medicion, 'form':None, 'resumen':calcular_especial(medicion),
        })
    form = EditarMedicionEspecialForm(request.POST or None, request.FILES or None, instance=medicion)
    if request.method == 'POST' and form.is_valid():
        accion = request.POST.get('accion', 'guardar')
        if accion not in ('guardar','validar'):
            raise PermissionDenied('Acción inválida.')
        with transaction.atomic():
            actual = MedicionEspecialSGR.objects.select_for_update().get(pk=medicion.pk)
            if actual.estado == MedicionEspecialSGR.Estado.VALIDADA:
                raise PermissionDenied('Otro administrador ya validó esta medición.')
            actual = form.save(commit=False)
            if accion == 'validar':
                actual.estado = MedicionEspecialSGR.Estado.VALIDADA
                actual.validado_por = request.user
                actual.validado_en = timezone.now()
            try:
                actual.full_clean()
            except ValidationError as exc:
                form.add_error(None, '; '.join(exc.messages))
            else:
                actual.save()
                AuditoriaMedicionEspecialSGR.objects.create(
                    medicion=actual, usuario=request.user,
                    accion='VALIDACION' if accion == 'validar' else 'EDICION',
                    descripcion=(f'Ítem: {actual.item.nombre}; tipo: {actual.item.clase}; '
                                 f'resueltos: {actual.resueltos}; recibidos: {actual.recibidos}; '
                                 f'Objetivo variable: {actual.objetivo_variable}; '
                                 f'Realizado variable: {actual.realizado_variable}; '
                                 f'fuente: {actual.fuente[:400]}'),
                )
                messages.success(request, 'Medición validada y calculada.' if accion == 'validar'
                                 else 'Borrador guardado sin puntuación.')
                return redirect('matriz_sgr:especial_editar', pk=actual.pk)
    return render(request, 'matriz_sgr/especiales_editar.html', {
        'medicion':medicion, 'form':form, 'resumen':calcular_especial(medicion),
    })


@login_required
@require_http_methods(['GET'])
def descargar_respaldo(request, pk):
    _exigir_admin(request.user)
    from pathlib import PurePosixPath
    from django.http import FileResponse, Http404
    medicion = get_object_or_404(MedicionEspecialSGR, pk=pk)
    if not medicion.respaldo:
        raise Http404('No hay respaldo asociado.')
    return FileResponse(medicion.respaldo.open('rb'), as_attachment=True,
                        filename=PurePosixPath(medicion.respaldo.name).name)
