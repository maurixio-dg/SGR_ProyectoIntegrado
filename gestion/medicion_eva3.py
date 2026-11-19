"""Gestión de metas por cargo/funcionario y ajustes de ausencias."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.http import HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .actividades_eva3 import es_admin
from .models import ConfiguracionMetaSGR, AusenciaSGR
from .operativa_eva3 import _metas_visibles, _delegaciones_usuario, _puede_gestionar_meta
from .operativa_eva3_forms import usuario_funcionario
from .medicion_eva3_forms import ConfiguracionMetaSGRForm, AusenciaSGRForm


def puede_registrar_ausencia(usuario):
    return es_admin(usuario) or (getattr(usuario, "rol", "") == "DELEG" and usuario_funcionario(usuario) is not None)


def _ausencias_visibles(usuario):
    lista = AusenciaSGR.objects.select_related("funcionario", "periodo", "registrado_por")
    if es_admin(usuario):
        return lista
    propio = usuario_funcionario(usuario)
    return lista.filter(funcionario__delegacion_id=propio.delegacion_id) if propio else lista.none()


@login_required
def configurar_meta_sgr(request, pk):
    if not _puede_gestionar_meta(request.user):
        raise PermissionDenied("Sin permisos para configurar metas.")
    meta = get_object_or_404(_metas_visibles(request.user), pk=pk)
    try:
        configuracion = meta.configuracion_sgr
    except ConfiguracionMetaSGR.DoesNotExist:
        configuracion = None
    formulario = ConfiguracionMetaSGRForm(
        request.POST or None, instance=configuracion, usuario=request.user, meta=meta
    )
    if request.method == "POST" and formulario.is_valid():
        with transaction.atomic():
            formulario.save()
        messages.success(request, "Configuración de meta guardada.")
        return redirect("gestion:indicadores")
    return render(request, "gestion/indicadores/configurar_sgr.html", {
        "formulario": formulario, "meta": meta,
    })


@login_required
def listar_ausencias_sgr(request):
    registros = _ausencias_visibles(request.user).order_by("-fecha_inicio", "-pk")
    return render(request, "gestion/indicadores/ausencias_sgr.html", {
        "registros": registros[:150], "puede_gestionar": puede_registrar_ausencia(request.user),
    })


@login_required
def registrar_ausencia_sgr(request):
    if not puede_registrar_ausencia(request.user):
        raise PermissionDenied("Solo el delegado o administrador puede registrar ausencias.")
    formulario = AusenciaSGRForm(request.POST or None, usuario=request.user)
    if request.method == "POST" and formulario.is_valid():
        with transaction.atomic():
            ausencia = formulario.save(commit=False)
            ausencia.registrado_por = request.user
            ausencia.full_clean()
            ausencia.save()
        messages.success(request, "Ausencia registrada correctamente.")
        return redirect("gestion:ausencias_sgr")
    return render(request, "gestion/indicadores/ausencia_form_sgr.html", {"formulario": formulario})


@login_required
@require_POST
def eliminar_ausencia_sgr(request, pk):
    if not puede_registrar_ausencia(request.user):
        raise PermissionDenied("Sin permisos para eliminar ausencias.")
    registro = get_object_or_404(_ausencias_visibles(request.user), pk=pk)
    registro.delete()
    messages.success(request, "Ausencia eliminada.")
    return redirect("gestion:ausencias_sgr")


@login_required
def auditoria_ponderaciones(request):
    if not _puede_gestionar_meta(request.user):
        raise PermissionDenied("Solo jefaturas y administración pueden auditar metas.")
    from .ponderaciones_sgr import resumen_por_ambitos, estado_cargo_matriz, config_de_meta
    from matriz_sgr.models import VinculoMatrizSGR
    metas=list(_metas_visibles(request.user).select_related('delegacion','periodo').all())
    grupos=resumen_por_ambitos(metas)
    alertas=[]
    vinculos=VinculoMatrizSGR.objects.filter(meta_id__in=[m.pk for m in metas]).select_related('item')
    por_meta={v.meta_id:v for v in vinculos}
    for meta in metas:
        v=por_meta.get(meta.pk)
        if not v:
            continue
        c=config_de_meta(meta)
        errores,_=estado_cargo_matriz(
            meta, c.funcionario if c and c.funcionario_id else None,
            c.cargo if c and c.cargo_id else None,
            c.funcion if c and c.funcion_id else None,
        )
        for mensaje in errores.values():
            alertas.append({'meta':meta,'item':v.item,'error':mensaje})
    return render(request,'gestion/indicadores/auditoria_ponderaciones.html',{
        'grupos':grupos,'alertas':alertas,
    })
