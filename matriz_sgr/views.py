"""Importación controlada de catálogos de la matriz y vinculación explícita a metas existentes."""
from collections import Counter
from decimal import Decimal
from hashlib import sha256
from pathlib import Path

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction, IntegrityError
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from gestion.models import MetaIndicador, ConfiguracionMetaSGR
from .forms import VincularMetaMatrizForm
from .lector_matriz import leer_matriz_xlsx, ErrorMatriz, MAX_BYTES
from .models import CatalogoMatrizSGR, ItemMatrizSGR, VinculoMatrizSGR

SESSION_KEY = 'matriz_sgr_importacion_pendiente'


def _admin(user):
    return user.is_authenticated and (user.is_superuser or getattr(user, 'rol', '') == 'ADMIN')


def _exigir_admin(user):
    if not _admin(user):
        raise PermissionDenied('Solo administración puede gestionar la matriz SGR.')


@login_required
def catalogos(request):
    _exigir_admin(request.user)
    lista = CatalogoMatrizSGR.objects.select_related('importado_por').prefetch_related('items')[:30]
    return render(request, 'matriz_sgr/catalogos.html', {'catalogos': lista})


@login_required
def importar(request):
    _exigir_admin(request.user)
    vista = {'muestra': [], 'resumen': {}, 'avisos': []}
    if request.method != 'POST':
        return render(request, 'matriz_sgr/importar.html', vista)
    accion = request.POST.get('accion', '')
    if accion == 'previsualizar':
        request.session.pop(SESSION_KEY, None)
        archivo = request.FILES.get('archivo')
        if not archivo or not archivo.name.lower().endswith('.xlsx'):
            messages.error(request, 'Selecciona la matriz municipal en formato .xlsx.')
            return render(request, 'matriz_sgr/importar.html', vista)
        if archivo.size > MAX_BYTES:
            messages.error(request, 'El archivo debe pesar menos de 8 MB.')
            return render(request, 'matriz_sgr/importar.html', vista)
        contenido = archivo.read(MAX_BYTES+1)
        try:
            items, avisos, resumen = leer_matriz_xlsx(contenido)
        except ErrorMatriz as exc:
            messages.error(request, str(exc))
            return render(request, 'matriz_sgr/importar.html', vista)
        if not items:
            messages.error(request, 'No se encontraron ítems de la matriz.')
            return render(request, 'matriz_sgr/importar.html', vista)
        digest = sha256(contenido).hexdigest()
        previo = CatalogoMatrizSGR.objects.filter(sha256=digest).first()
        if previo:
            messages.info(request, 'Esta versión de la matriz ya fue importada.')
            return redirect('matriz_sgr:detalle', pk=previo.pk)
        request.session[SESSION_KEY] = {
            'items':items, 'sha256':digest, 'nombre_archivo':Path(archivo.name).name[:255],
        }
        vista.update({'muestra':items[:15], 'resumen':resumen, 'avisos':avisos[:10],
                     'confirmable':True, 'cantidad':len(items), 'cantidad_avisos':len(avisos)})
        return render(request, 'matriz_sgr/importar.html', vista)
    if accion == 'confirmar':
        previo = request.session.pop(SESSION_KEY, None)
        if not previo or not previo.get('items') or len(previo.get('sha256','')) != 64:
            messages.error(request, 'La previsualización caducó; vuelve a seleccionar el Excel.')
            return redirect('matriz_sgr:importar')
        with transaction.atomic():
            catalogo = CatalogoMatrizSGR.objects.filter(sha256=previo['sha256']).first()
            if not catalogo:
                catalogo = CatalogoMatrizSGR.objects.create(
                    sha256=previo['sha256'], nombre_archivo=previo['nombre_archivo'],
                    importado_por=request.user,
                )
                ItemMatrizSGR.objects.bulk_create([
                    ItemMatrizSGR(catalogo=catalogo, **fila) for fila in previo['items']
                ], batch_size=200)
        messages.success(request, 'Matriz incorporada al catálogo correctamente.')
        return redirect('matriz_sgr:detalle', pk=catalogo.pk)
    messages.error(request, 'Acción no reconocida.')
    return redirect('matriz_sgr:importar')


@login_required
def detalle(request, pk):
    _exigir_admin(request.user)
    catalogo = get_object_or_404(CatalogoMatrizSGR, pk=pk)
    qs = catalogo.items.prefetch_related('vinculos__meta__periodo','vinculos__meta__delegacion').all()
    hoja = request.GET.get('hoja','')
    clase = request.GET.get('clase','')
    if hoja and hoja in set(catalogo.items.values_list('hoja', flat=True)):
        qs = qs.filter(hoja=hoja)
    if clase and clase in ItemMatrizSGR.Clase.values:
        qs = qs.filter(clase=clase)
    items = list(qs.order_by('hoja','fila'))
    total = catalogo.items.count()
    resumen = dict(Counter(catalogo.items.values_list('clase', flat=True)))
    return render(request, 'matriz_sgr/detalle.html', {
        'catalogo':catalogo, 'items':items,
        'hojas':sorted(set(catalogo.items.values_list('hoja', flat=True))),
        'hoja_actual':hoja, 'clase_actual':clase, 'clases':ItemMatrizSGR.Clase.choices,
        'total':total, 'resumen':resumen,
    })


@login_required
def vincular(request, pk):
    _exigir_admin(request.user)
    item = get_object_or_404(ItemMatrizSGR.objects.select_related('catalogo'), pk=pk)
    if not item.es_vinculable:
        messages.error(request, 'Esta meta requiere revisión de su unidad o fórmula antes de vincularla.')
        return redirect('matriz_sgr:detalle', pk=item.catalogo_id)
    form = VincularMetaMatrizForm(request.POST or None, item=item)
    if request.method == 'POST' and form.is_valid():
        delegacion = form.cleaned_data['delegacion']
        periodo = form.cleaned_data['periodo']
        funcionario = form.cleaned_data['funcionario']
        cargo = form.cleaned_data['cargo'] or (funcionario.cargo if funcionario else None)
        # Identificador legible y único por ítem/alcance; no modifica metas existentes.
        sufijo = f' · F{funcionario.pk}' if funcionario else ' · General'
        nombre = (item.nombre[:95] + ' · ' + item.hoja.strip()[:36] + sufijo)[:160]
        try:
            with transaction.atomic():
                meta = MetaIndicador(
                    nombre=nombre, delegacion=delegacion, periodo=periodo,
                    meta_cantidad=int(item.meta_original), ponderacion=item.ponderacion,
                    activo=True,
                )
                meta.full_clean()
                meta.save()
                config = ConfiguracionMetaSGR(
                    meta=meta, funcionario=funcionario, cargo=cargo,
                    tope_porcentaje=Decimal('120.00'),
                )
                config.full_clean()
                config.save()
                VinculoMatrizSGR.objects.create(item=item, meta=meta, creado_por=request.user)
        except (ValidationError, IntegrityError) as exc:
            form.add_error(None, 'No se pudo crear la meta: comprueba que no exista otra con el mismo nombre, período y delegación.')
        else:
            messages.success(request, 'Meta creada en Indicadores con ponderación municipal y tope de 120 %.')
            return redirect('matriz_sgr:detalle', pk=item.catalogo_id)
    return render(request, 'matriz_sgr/vincular.html', {'item':item, 'formulario':form})
