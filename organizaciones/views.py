"""Catastro municipal, CRUD y previsualización/importación de Excel."""
from io import BytesIO
from pathlib import Path
from uuid import uuid4
import re

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core import signing
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from funcionarios.models import Funcionario

from .forms import OrganizacionForm
from .models import OrganizacionComunitaria
from .xlsx_import import ErrorExcel, MAX_BYTES, leer_catastro_xlsx

TOKEN_SALT = 'sgr-organizaciones-eva4-1h'


def _es_admin(usuario):
    return usuario.is_authenticated and (usuario.is_superuser or getattr(usuario, 'rol', '') == 'ADMIN')


def _exigir_admin(usuario):
    if not _es_admin(usuario):
        raise PermissionDenied('Solo administración puede modificar el catastro.')


def _visibles(usuario):
    registros = OrganizacionComunitaria.objects.select_related('delegacion')
    if _es_admin(usuario):
        return registros
    funcionario = Funcionario.objects.filter(usuario=usuario).first()
    if not funcionario:
        return registros.none()
    # Catastros no verificados o sin delegación asignada son exclusivos de administración.
    return registros.filter(delegacion_id=funcionario.delegacion_id,
                            estado_verificacion=OrganizacionComunitaria.Verificacion.VERIFICADA)


@login_required
def listar(request):
    qs = _visibles(request.user)
    total_disponibles = qs.count()
    buscar = request.GET.get('buscar', '').strip()[:120]
    tipo = request.GET.get('tipo', '').strip()
    estado = request.GET.get('estado', '').strip()
    territorio = request.GET.get('territorio', '').strip()[:80]
    if buscar:
        qs = qs.filter(Q(nombre__icontains=buscar) | Q(domicilio_legal__icontains=buscar)
                       | Q(numero_registro_pj__icontains=buscar))
    if tipo in OrganizacionComunitaria.Tipo.values:
        qs = qs.filter(tipo=tipo)
    if estado in OrganizacionComunitaria.Verificacion.values:
        qs = qs.filter(estado_verificacion=estado)
    if territorio:
        qs = qs.filter(territorio_origen__icontains=territorio)
    pagina = Paginator(qs, 25).get_page(request.GET.get('pagina'))
    return render(request, 'organizaciones/listar.html', {
        'pagina': pagina, 'buscar': buscar, 'tipo_actual': tipo, 'estado_actual': estado,
        'territorio_actual': territorio, 'tipos': OrganizacionComunitaria.Tipo.choices,
        'estados': OrganizacionComunitaria.Verificacion.choices,
        'puede_editar': _es_admin(request.user),
        'total_disponibles': total_disponibles,
        'filtros_activos': bool(buscar or tipo or estado or territorio),
    })


@login_required
def crear(request):
    _exigir_admin(request.user)
    form = OrganizacionForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        registro = form.save(commit=False)
        registro.creado_por = request.user
        registro.full_clean()
        registro.save()
        messages.success(request, 'Organización registrada correctamente.')
        return redirect('organizaciones:listar')
    return render(request, 'organizaciones/formulario.html', {'formulario': form, 'titulo': 'Nueva organización'})


@login_required
def editar(request, pk):
    _exigir_admin(request.user)
    registro = get_object_or_404(OrganizacionComunitaria, pk=pk)
    form = OrganizacionForm(request.POST or None, instance=registro)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Organización actualizada correctamente.')
        return redirect('organizaciones:listar')
    return render(request, 'organizaciones/formulario.html', {'formulario': form,
                   'titulo': 'Editar organización', 'registro': registro})


@login_required
def eliminar(request, pk):
    _exigir_admin(request.user)
    registro = get_object_or_404(OrganizacionComunitaria, pk=pk)
    if request.method == 'POST':
        registro.delete()
        messages.success(request, 'Organización eliminada.')
        return redirect('organizaciones:listar')
    return render(request, 'organizaciones/confirmar_eliminar.html', {'registro': registro})


def _plan_importacion(registros):
    # Se evita multiplicar consultas por fila: una consulta de registros y una de nombres.
    existentes_registro = set(filter(None, OrganizacionComunitaria.objects.values_list('numero_registro_pj', flat=True)))
    existentes_sin_registro = set(
        (o.nombre.strip().casefold(), o.territorio_origen.strip().casefold())
        for o in OrganizacionComunitaria.objects.filter(numero_registro_pj__isnull=True).only('nombre', 'territorio_origen')
    )
    nuevos, vistas_registro, vistas_sin_registro = [], set(), set()
    duplicados = 0
    for registro in registros:
        identificador = registro['numero_registro_pj']
        nombre_territorio = (registro['nombre'].casefold(), registro['territorio_origen'].casefold())
        if identificador:
            repetido = identificador in existentes_registro or identificador in vistas_registro
            vistas_registro.add(identificador)
        else:
            repetido = nombre_territorio in existentes_sin_registro or nombre_territorio in vistas_sin_registro
            vistas_sin_registro.add(nombre_territorio)
        if repetido:
            duplicados += 1
            continue
        nuevos.append(registro)
    return nuevos, duplicados


def _directorio_temporal():
    ruta = Path(settings.BASE_DIR) / '.sgr_importaciones_pendientes'
    ruta.mkdir(mode=0o700, parents=True, exist_ok=True)
    return ruta


@login_required
def importar_excel(request):
    _exigir_admin(request.user)
    datos = {'muestra': [], 'avisos': []}
    if request.method != 'POST':
        return render(request, 'organizaciones/importar.html', datos)

    accion = request.POST.get('accion')
    if accion == 'previsualizar':
        excel = request.FILES.get('archivo')
        if not excel:
            messages.error(request, 'Selecciona un archivo .xlsx.')
            return render(request, 'organizaciones/importar.html', datos)
        if not excel.name.lower().endswith('.xlsx') or excel.size > MAX_BYTES:
            messages.error(request, 'Se requiere un .xlsx de máximo 10 MB.')
            return render(request, 'organizaciones/importar.html', datos)
        contenido = excel.read(MAX_BYTES + 1)
        try:
            registros, avisos = leer_catastro_xlsx(BytesIO(contenido))
        except (ErrorExcel, ValueError) as e:
            messages.error(request, str(e))
            return render(request, 'organizaciones/importar.html', datos)
        nuevos, duplicados = _plan_importacion(registros)
        ident = uuid4().hex
        ( _directorio_temporal() / (ident + '.xlsx') ).write_bytes(contenido)
        token = signing.dumps({'id': ident, 'usuario': request.user.pk,
                               'nombre': Path(excel.name).name[:255]}, salt=TOKEN_SALT)
        datos.update({
            'token': token, 'muestra': registros[:10], 'total': len(registros),
            'nuevos': len(nuevos), 'duplicados': duplicados,
            'sin_domicilio': sum(not r['domicilio_legal'] for r in registros),
            'sin_territorio': sum(not r['territorio_origen'] for r in registros),
            'avisos': avisos[:20], 'avisos_total': len(avisos),
            'nombre_excel': Path(excel.name).name,
        })
        return render(request, 'organizaciones/importar.html', datos)

    if accion == 'confirmar':
        try:
            firmados = signing.loads(request.POST.get('token', ''), salt=TOKEN_SALT, max_age=3600)
        except signing.BadSignature:
            messages.error(request, 'La previsualización venció. Vuelve a seleccionar el Excel.')
            return redirect('organizaciones:importar')
        if firmados.get('usuario') != request.user.pk or not re.fullmatch(r'[0-9a-f]{32}', str(firmados.get('id'))):
            raise PermissionDenied('No tienes autorización para importar ese archivo.')
        ruta = _directorio_temporal() / (firmados['id'] + '.xlsx')
        if not ruta.is_file():
            raise Http404('El Excel temporal ya no está disponible.')
        try:
            with ruta.open('rb') as archivo:
                registros, _ = leer_catastro_xlsx(archivo)
            # Transacción única: o se incorporan los registros válidos o ninguno.
            with transaction.atomic():
                nuevos, duplicados = _plan_importacion(registros)
                objetos = [OrganizacionComunitaria(
                    **r, creado_por=request.user,
                    fuente_archivo=firmados['nombre'],
                    tipo=OrganizacionComunitaria.Tipo.SIN_CLASIFICAR,
                    estado_verificacion=OrganizacionComunitaria.Verificacion.PENDIENTE,
                ) for r in nuevos]
                OrganizacionComunitaria.objects.bulk_create(objetos, batch_size=250)
        except ErrorExcel as e:
            messages.error(request, str(e))
            return redirect('organizaciones:importar')
        finally:
            ruta.unlink(missing_ok=True)
        messages.success(request, f'Importación completada: {len(nuevos)} organizaciones incorporadas, '
                         f'{duplicados} duplicados omitidos. Todas pendientes de verificación.')
        return redirect('organizaciones:listar')

    messages.error(request, 'Acción de importación no reconocida.')
    return redirect('organizaciones:importar')
