"""CRUD del Tubo con alcances de datos por delegación y propiedad."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models.deletion import ProtectedError
from django.db.models import Q
from django.http import FileResponse, Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.utils import timezone
from django.views.decorators.http import require_POST, require_safe
from django.core.paginator import Paginator

from funcionarios.models import Funcionario
from .forms import VecinoForm, GestionForm, CartaForm, TerritorioForm, TipoForm, SubtipoForm
from .models import Vecino, Territorio, TipoAtencion, SubtipoAtencion, GestionSocial, HitoGestion, HistorialGestion, CartaTubo, VinculoGestionActividad
from .integracion_metas import puede_vincular_meta
from .permisos import (es_admin, funcionario_usuario, delegacion_usuario, visibles,
                       puede_crear, puede_editar_gestion, puede_revisar, puede_editar_carta)


def _admin_o_403(user):
    if not es_admin(user):
        raise PermissionDenied('Solo administración puede gestionar catálogos.')


def _crear_o_403(user):
    if not puede_crear(user):
        raise PermissionDenied('No tiene permisos para registrar solicitudes.')


@login_required
def listar_gestiones(request):
    registros = visibles(GestionSocial, request.user).select_related('delegacion','vecino','responsable','tipo')
    buscar = request.GET.get('buscar','').strip()[:150]
    estado = request.GET.get('estado','').strip()
    desde = request.GET.get('desde','').strip()
    hasta = request.GET.get('hasta','').strip()
    responsable = request.GET.get('responsable','').strip()
    solo = request.GET.get('en_tubo','').strip()
    if buscar:
        filtro = (Q(vecino__nombre__icontains=buscar) | Q(vecino__rut__icontains=buscar) |
                  Q(titulo__icontains=buscar) | Q(descripcion__icontains=buscar))
        # Código automático: SGR-TUB-000123 o número exacto.
        texto = buscar.upper()
        codigo = texto.removeprefix('SGR-TUB-')
        if codigo.isdigit():
            filtro |= Q(pk=int(codigo))
        registros = registros.filter(filtro)
    if estado in dict(GestionSocial.Estado.choices):
        registros = registros.filter(estado=estado)
    if desde:
        from datetime import date
        try: registros=registros.filter(fecha_registro__date__gte=date.fromisoformat(desde))
        except ValueError: desde=''
    if hasta:
        from datetime import date
        try: registros=registros.filter(fecha_registro__date__lte=date.fromisoformat(hasta))
        except ValueError: hasta=''
    if responsable.isdigit():
        registros=registros.filter(responsable_id=int(responsable))
    if solo in ('si','no'):
        registros=registros.filter(ingresa_tubo=(solo=='si'))
    propios = Funcionario.objects.all() if es_admin(request.user) else Funcionario.objects.filter(delegacion_id=delegacion_usuario(request.user))
    pagina = Paginator(registros, 20).get_page(request.GET.get('pagina'))
    contexto = {
        'pagina':pagina, 'buscar':buscar, 'estado':estado, 'desde':desde, 'hasta':hasta,
        'responsable':responsable,'en_tubo':solo,'responsables':propios,'estados':GestionSocial.Estado.choices,
        'puede_crear':puede_crear(request.user),
    }
    if request.GET.get('live') == '1':
        return JsonResponse({'html':render_to_string('tubo/_filas_gestiones.html',contexto,request=request),
                             'total':pagina.paginator.count})
    return render(request,'tubo/gestiones.html',contexto)


@login_required
def nueva_gestion(request):
    _crear_o_403(request.user)
    formulario = GestionForm(request.POST or None,request.FILES or None,usuario=request.user)
    if request.method=='POST' and formulario.is_valid():
        with transaction.atomic():
            gestion=formulario.save(commit=False)
            gestion.creado_por=request.user
            gestion.full_clean()
            gestion.save()
            HistorialGestion.objects.create(gestion=gestion, usuario=request.user, accion='CREACION',
                descripcion='Solicitud o gestión social registrada')
        messages.success(request,'Gestión registrada correctamente.')
        return redirect('tubo:detalle_gestion',pk=gestion.pk)
    return render(request,'tubo/formulario.html',{'formulario':formulario,'titulo':'Nueva gestión social', 'volver':'tubo:gestiones'})


@login_required
def editar_gestion(request,pk):
    gestion=get_object_or_404(visibles(GestionSocial,request.user),pk=pk)
    if not puede_editar_gestion(request.user,gestion):
        if request.method=='GET':
            return redirect('tubo:detalle_gestion',pk=pk)
        raise PermissionDenied('La gestión aprobada o ajena no puede modificarse.')
    formulario=GestionForm(request.POST or None,request.FILES or None,instance=gestion,usuario=request.user)
    if request.method=='POST' and formulario.is_valid():
        with transaction.atomic():
            # Repetir el control con bloqueo para evitar carreras con la aprobación.
            actual=get_object_or_404(GestionSocial.objects.select_for_update(),pk=pk)
            if not puede_editar_gestion(request.user,actual):
                raise PermissionDenied('La gestión ya no admite edición.')
            nuevo=formulario.save(commit=False)
            nuevo.estado=actual.estado
            nuevo.creado_por=actual.creado_por
            nuevo.full_clean()
            nuevo.save()
            HistorialGestion.objects.create(gestion=nuevo,usuario=request.user,accion='EDICION',
                descripcion='Datos de la gestión actualizados')
        messages.success(request,'Gestión actualizada correctamente.')
        return redirect('tubo:detalle_gestion',pk=pk)
    return render(request,'tubo/formulario.html',{'formulario':formulario,'titulo':'Editar gestión', 'volver':'tubo:gestiones'})


@login_required
@require_safe
def detalle_gestion(request,pk):
    gestion=get_object_or_404(visibles(GestionSocial,request.user).select_related('vecino','responsable','delegacion','tipo','subtipo'),pk=pk)
    vinculo_actividad = VinculoGestionActividad.objects.select_related('actividad', 'actividad__asignacion_meta_eva3__meta').filter(gestion=gestion).first()
    return render(request,'tubo/detalle_gestion.html',{
        'gestion':gestion, 'puede_editar':puede_editar_gestion(request.user,gestion),
        'vinculo_actividad': vinculo_actividad,
        'puede_vincular_meta': puede_vincular_meta(request.user, gestion) and vinculo_actividad is None,
        'puede_revisar':puede_revisar(request.user,gestion),
        'hitos':gestion.hitos.select_related('creado_por'),
        'historial':gestion.historial.select_related('usuario')[:20],
        'decisiones':[(GestionSocial.Estado.EN_PROCESO,'En proceso'),
                     (GestionSocial.Estado.MAS_ANTECEDENTES,'Solicitar más antecedentes'),
                     (GestionSocial.Estado.APROBADA,'Aprobar'),
                     (GestionSocial.Estado.RECHAZADA,'Rechazar')]
    })


@login_required
@require_POST
def anotar_hito(request,pk):
    gestion=get_object_or_404(visibles(GestionSocial,request.user),pk=pk)
    if not puede_editar_gestion(request.user,gestion):
        raise PermissionDenied('No puede añadir hitos a esta gestión.')
    descripcion=request.POST.get('descripcion','').strip()
    if not 5<=len(descripcion)<=3000:
        messages.error(request,'El hito debe tener entre 5 y 3000 caracteres.')
        return redirect('tubo:detalle_gestion',pk=pk)
    with transaction.atomic():
        registro=GestionSocial.objects.select_for_update().get(pk=pk)
        if not puede_editar_gestion(request.user,registro):
            raise PermissionDenied('El registro ya se aprobó o no le pertenece.')
        HitoGestion.objects.create(gestion=registro,descripcion=descripcion,creado_por=request.user)
        HistorialGestion.objects.create(gestion=registro,usuario=request.user,accion='HITO',descripcion=descripcion)
    messages.success(request,'Hito registrado correctamente.')
    return redirect('tubo:detalle_gestion',pk=pk)


@login_required
@require_POST
def resolver_gestion(request,pk):
    gestion=get_object_or_404(visibles(GestionSocial,request.user),pk=pk)
    if not puede_revisar(request.user,gestion):
        raise PermissionDenied('No puede revisar esta gestión.')
    estado=request.POST.get('estado','')
    estados=[GestionSocial.Estado.EN_PROCESO,GestionSocial.Estado.MAS_ANTECEDENTES,
             GestionSocial.Estado.APROBADA,GestionSocial.Estado.RECHAZADA]
    if estado not in estados:
        raise PermissionDenied('Decisión de revisión inválida.')
    comentario=request.POST.get('comentario','').strip()[:3000]
    if estado in (GestionSocial.Estado.RECHAZADA,GestionSocial.Estado.MAS_ANTECEDENTES) and len(comentario)<5:
        messages.error(request,'Explique el motivo de la solicitud o rechazo (mínimo 5 caracteres).')
        return redirect('tubo:detalle_gestion',pk=pk)
    with transaction.atomic():
        registro=GestionSocial.objects.select_for_update().get(pk=pk)
        if not puede_revisar(request.user,registro):
            raise PermissionDenied('Esta gestión ya fue cerrada o no tiene permisos.')
        registro.estado=estado
        registro.revisado_por=request.user
        registro.fecha_revision=timezone.now()
        registro.full_clean()
        registro.save(update_fields=['estado','revisado_por','fecha_revision','actualizado_en'])
        HistorialGestion.objects.create(gestion=registro,usuario=request.user,accion='REVISION',
            descripcion=f'{registro.get_estado_display()}: {comentario}')
    messages.success(request,'Estado actualizado correctamente.')
    return redirect('tubo:detalle_gestion',pk=pk)


@login_required
def vecinos(request):
    lista=visibles(Vecino,request.user).select_related('delegacion')
    buscar=request.GET.get('buscar','').strip()[:100]
    if buscar:
        lista=lista.filter(Q(nombre__icontains=buscar)|Q(rut__icontains=buscar)|Q(telefono__icontains=buscar))
    pagina=Paginator(lista,20).get_page(request.GET.get('pagina'))
    pagina.object_list=list(pagina.object_list)
    for v in pagina.object_list:
        v.puede_editar_web = (puede_crear(request.user) and
                              (es_admin(request.user) or v.creado_por_id == request.user.pk))
    return render(request,'tubo/vecinos.html',{'pagina':pagina,'buscar':buscar,'puede_crear':puede_crear(request.user)})


@login_required
def formulario_vecino(request,pk=None):
    _crear_o_403(request.user)
    vecino=get_object_or_404(visibles(Vecino,request.user),pk=pk) if pk else None
    if vecino and not (es_admin(request.user) or vecino.creado_por_id == request.user.pk):
        raise PermissionDenied('Solo el creador o administración puede editar datos del vecino.')
    formulario=VecinoForm(request.POST or None,instance=vecino,usuario=request.user)
    if request.method=='POST' and formulario.is_valid():
        dato=formulario.save(commit=False)
        if not vecino:
            dato.creado_por=request.user
        dato.full_clean()
        dato.save()
        messages.success(request,'Vecino guardado correctamente.')
        return redirect('tubo:vecinos')
    return render(request,'tubo/formulario.html',{'formulario':formulario,'titulo':'Editar vecino' if vecino else 'Registrar vecino', 'volver':'tubo:vecinos'})


@login_required
def cartas(request):
    lista=visibles(CartaTubo,request.user).select_related('delegacion','gestion')
    buscar=request.GET.get('buscar','').strip()[:100]
    if buscar:
        lista=lista.filter(Q(asunto__icontains=buscar)|Q(destinatario__icontains=buscar)|Q(numero_oficio__icontains=buscar))
    pagina=Paginator(lista,20).get_page(request.GET.get('pagina'))
    return render(request,'tubo/cartas.html',{'pagina':pagina,'buscar':buscar,'puede_crear':puede_crear(request.user)})


@login_required
def formulario_carta(request,pk=None):
    _crear_o_403(request.user)
    carta=get_object_or_404(visibles(CartaTubo,request.user),pk=pk) if pk else None
    if carta and not puede_editar_carta(request.user,carta):
        if request.method=='GET':
            return redirect('tubo:detalle_carta',pk=pk)
        raise PermissionDenied('Carta cerrada o sin permisos.')
    formulario=CartaForm(request.POST or None,request.FILES or None,instance=carta,usuario=request.user)
    if request.method=='POST' and formulario.is_valid():
        with transaction.atomic():
            if carta:
                actual=CartaTubo.objects.select_for_update().get(pk=pk)
                if not puede_editar_carta(request.user,actual):
                    raise PermissionDenied('Carta cerrada o sin permisos.')
            dato=formulario.save(commit=False)
            if not carta:
                dato.creado_por=request.user
            dato.full_clean()
            dato.save()
        messages.success(request,'Carta guardada correctamente.')
        return redirect('tubo:detalle_carta',pk=dato.pk)
    return render(request,'tubo/formulario.html',{'formulario':formulario,'titulo':'Editar carta' if carta else 'Nueva carta', 'volver':'tubo:cartas'})


@login_required
@require_safe
def detalle_carta(request,pk):
    carta=get_object_or_404(visibles(CartaTubo,request.user).select_related('delegacion','gestion'),pk=pk)
    return render(request,'tubo/detalle_carta.html',{'carta':carta,'puede_editar':puede_editar_carta(request.user,carta)})


@login_required
@require_safe
def subtipos_por_tipo(request):
    tipo=request.GET.get('tipo','')
    if not tipo.isdigit():
        return JsonResponse({'resultados': []})
    qs=SubtipoAtencion.objects.filter(activo=True,tipo_id=int(tipo)).order_by('nombre').values('id','nombre')
    return JsonResponse({'resultados':list(qs)})


@login_required
@require_safe
def descargar_archivo(request,clase,pk):
    if clase == 'gestion':
        obj=get_object_or_404(visibles(GestionSocial,request.user),pk=pk)
        campo=obj.evidencia
    elif clase == 'carta':
        obj=get_object_or_404(visibles(CartaTubo,request.user),pk=pk)
        campo=obj.adjunto
    else:
        raise Http404('Archivo no encontrado.')
    if not campo:
        raise Http404('No hay archivo adjunto.')
    return FileResponse(campo.open('rb'),as_attachment=True,filename=campo.name.rsplit('/',1)[-1])


CATALOGOS={
    'territorios':(Territorio,TerritorioForm),
    'tipos':(TipoAtencion,TipoForm),
    'subtipos':(SubtipoAtencion,SubtipoForm),
}


@login_required
def listar_catalogo(request,clase):
    _admin_o_403(request.user)
    if clase not in CATALOGOS:
        raise Http404('Catálogo inexistente.')
    modelo,_=CATALOGOS[clase]
    return render(request,'tubo/catalogo.html',{'clase':clase,'registros':modelo.objects.all(), 'titulo':clase.capitalize()})


@login_required
def formulario_catalogo(request,clase,pk=None):
    _admin_o_403(request.user)
    if clase not in CATALOGOS:
        raise Http404('Catálogo inexistente.')
    modelo,forma=CATALOGOS[clase]
    obj=get_object_or_404(modelo,pk=pk) if pk else None
    formulario=forma(request.POST or None,instance=obj)
    if request.method=='POST' and formulario.is_valid():
        dato=formulario.save(commit=False)
        dato.full_clean()
        dato.save()
        messages.success(request,'Catálogo guardado correctamente.')
        return redirect('tubo:catalogo',clase=clase)
    return render(request,'tubo/formulario.html',{'formulario':formulario,'titulo':f'{"Editar" if obj else "Crear"} {clase}', 'volver_catalogo':clase})


@login_required
@require_POST
def eliminar_vecino(request,pk):
    _crear_o_403(request.user)
    vecino=get_object_or_404(visibles(Vecino,request.user),pk=pk)
    if not (es_admin(request.user) or vecino.creado_por_id == request.user.pk):
        raise PermissionDenied('Solo quien registró al vecino o administración puede eliminarlo.')
    try:
        vecino.delete()
        messages.success(request,'Vecino eliminado.')
    except ProtectedError:
        messages.error(request,'No se puede eliminar: tiene gestiones vinculadas. Conserve su historial.')
    return redirect('tubo:vecinos')


@login_required
@require_POST
def eliminar_catalogo(request,clase,pk):
    _admin_o_403(request.user)
    if clase not in CATALOGOS:
        raise Http404('Catálogo inexistente.')
    modelo,_ = CATALOGOS[clase]
    registro=get_object_or_404(modelo,pk=pk)
    try:
        registro.delete()
        messages.success(request,'Registro de catálogo eliminado.')
    except ProtectedError:
        messages.error(request,'No se puede eliminar: está siendo utilizado. Desactívelo desde Editar.')
    return redirect('tubo:catalogo',clase=clase)
