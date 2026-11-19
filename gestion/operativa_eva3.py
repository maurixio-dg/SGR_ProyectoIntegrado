"""CRUD Agenda, Metas/Indicadores, validación de actividades e informes de EVA3."""
import csv
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Q
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from delegaciones.models import Delegacion
from funcionarios.models import Funcionario
from .actividades_eva3 import actividades_visibles, es_admin
from .models import (Actividad, Periodo, AgendaCompromiso, MetaIndicador,
                     ActividadRevision, ActividadIndicador)
from .operativa_eva3_forms import (AgendaForm, MetaIndicadorForm,
                                  RevisionActividadConMetaForm, es_jefatura,
                                  usuario_funcionario)


def _delegaciones_usuario(usuario):
    if es_admin(usuario):
        return Delegacion.objects.all()
    propio = usuario_funcionario(usuario)
    return Delegacion.objects.filter(pk=propio.delegacion_id) if propio else Delegacion.objects.none()


def _agenda_visibles(usuario):
    lista = AgendaCompromiso.objects.select_related("delegacion", "responsable", "periodo", "actividad", "creado_por")
    if es_admin(usuario):
        return lista
    propio = usuario_funcionario(usuario)
    if not propio:
        return lista.none()
    if es_jefatura(usuario) or getattr(usuario, "rol", "") in ("VERIF", "CONS"):
        return lista.filter(delegacion_id=propio.delegacion_id)
    return lista.filter(responsable_id=propio.pk)


def _metas_visibles(usuario):
    lista = MetaIndicador.objects.select_related("delegacion", "periodo")
    if es_admin(usuario):
        return lista
    propio = usuario_funcionario(usuario)
    return lista.filter(delegacion_id=propio.delegacion_id) if propio else lista.none()


def _puede_crear_agenda(usuario):
    return es_admin(usuario) or (getattr(usuario, "rol", "") not in ("VERIF", "CONS") and bool(usuario_funcionario(usuario)))


def _puede_editar_agenda(usuario, compromiso):
    if es_admin(usuario):
        return True
    propio = usuario_funcionario(usuario)
    if not propio:
        return False
    return (compromiso.delegacion_id == propio.delegacion_id and es_jefatura(usuario)) or compromiso.creado_por_id == usuario.pk


def _puede_gestionar_meta(usuario):
    return es_jefatura(usuario) and (es_admin(usuario) or bool(usuario_funcionario(usuario)))


def _validadores_pueden_revisar(usuario, actividad):
    if es_admin(usuario):
        return True
    if getattr(usuario, "rol", "") not in ("VERIF", "COORD", "DELEG"):
        return False
    propio = usuario_funcionario(usuario)
    return bool(propio and propio.delegacion_id == actividad.delegacion_id and actividad.creado_por_id != usuario.pk)


def _filtrar_periodo_delegacion(actividades, request):
    """Filtros auditables: jamás amplían el ámbito de acceso del usuario."""
    periodo_id = request.GET.get("periodo", "").strip()
    delegacion_id = request.GET.get("delegacion", "").strip()
    if periodo_id.isdecimal():
        periodo = Periodo.objects.filter(pk=int(periodo_id)).first()
        if periodo:
            actividades = actividades.filter(fecha_actividad__range=(periodo.fecha_inicio, periodo.fecha_fin))
    if delegacion_id.isdecimal():
        actividades = actividades.filter(delegacion_id=int(delegacion_id))
    return actividades


@login_required
def agenda_colectiva(request):
    registros = _agenda_visibles(request.user)
    buscar = request.GET.get("buscar", "").strip()
    estado = request.GET.get("estado", "").strip()
    if buscar:
        registros = registros.filter(Q(titulo__icontains=buscar) | Q(descripcion__icontains=buscar) | Q(responsable__nombre__icontains=buscar))
    if estado in dict(AgendaCompromiso.Estado.choices):
        registros = registros.filter(estado=estado)
    from django.core.paginator import Paginator
    pagina = Paginator(registros, 20).get_page(request.GET.get("pagina"))
    return render(request, "gestion/agenda/listar_eva3.html", {
        "pagina": pagina, "buscar": buscar, "estado": estado,
        "estados": AgendaCompromiso.Estado.choices,
        "puede_crear": _puede_crear_agenda(request.user),
    })


@login_required
def nuevo_compromiso(request):
    if not _puede_crear_agenda(request.user):
        raise PermissionDenied("Sin permisos para registrar compromisos.")
    formulario = AgendaForm(request.POST or None, usuario=request.user)
    if request.method == "POST" and formulario.is_valid():
        compromiso = formulario.save(commit=False)
        compromiso.creado_por = request.user
        compromiso.full_clean()
        compromiso.save()
        messages.success(request, "Compromiso registrado correctamente.")
        return redirect("gestion:agenda_colectiva")
    return render(request, "gestion/agenda/formulario_eva3.html", {"formulario": formulario, "titulo": "Nuevo compromiso"})


@login_required
def editar_compromiso(request, pk):
    compromiso = get_object_or_404(_agenda_visibles(request.user), pk=pk)
    if not _puede_editar_agenda(request.user, compromiso):
        raise PermissionDenied("No puede editar este compromiso.")
    formulario = AgendaForm(request.POST or None, instance=compromiso, usuario=request.user)
    if request.method == "POST" and formulario.is_valid():
        registro = formulario.save(commit=False)
        registro.full_clean()
        registro.save()
        messages.success(request, "Compromiso actualizado correctamente.")
        return redirect("gestion:agenda_colectiva")
    return render(request, "gestion/agenda/formulario_eva3.html", {"formulario": formulario, "titulo": "Editar compromiso"})


@login_required
def detalle_compromiso(request, codigo):
    if not codigo.startswith("SGR-AG-") or not codigo[7:].isdigit():
        raise Http404("Compromiso no encontrado.")
    compromiso = get_object_or_404(_agenda_visibles(request.user), pk=int(codigo[7:]))
    return render(request, "gestion/agenda/detalle_eva3.html", {
        "compromiso": compromiso,
        "puede_editar": _puede_editar_agenda(request.user, compromiso),
    })


@login_required
@require_POST
def eliminar_compromiso(request, pk):
    compromiso = get_object_or_404(_agenda_visibles(request.user), pk=pk)
    if not _puede_editar_agenda(request.user, compromiso):
        raise PermissionDenied("No puede eliminar este compromiso.")
    compromiso.delete()
    messages.success(request, "Compromiso eliminado correctamente.")
    return redirect("gestion:agenda_colectiva")


def _resumen_meta(meta):
    from .medicion_eva3_calculos import calcular_resumen_meta
    return calcular_resumen_meta(meta)


@login_required
def indicadores(request):
    metas = _metas_visibles(request.user).filter(activo=True)
    periodo = request.GET.get("periodo", "").strip()
    if periodo.isdecimal():
        metas = metas.filter(periodo_id=int(periodo))
    delegacion = request.GET.get("delegacion", "").strip()
    if delegacion.isdecimal():
        metas = metas.filter(delegacion_id=int(delegacion))
    resumenes = [_resumen_meta(meta) for meta in metas]
    # Nota: es un resumen básico; la matriz SGR municipal requiere reglas adicionales.
    return render(request, "gestion/indicadores/listar_eva3.html", {
        "resumenes": resumenes, "periodos": Periodo.objects.all(),
        "delegaciones": _delegaciones_usuario(request.user),
        "periodo_actual": periodo, "delegacion_actual": delegacion,
        "puede_gestionar": _puede_gestionar_meta(request.user),
    })


@login_required
def nueva_meta(request):
    if not _puede_gestionar_meta(request.user):
        raise PermissionDenied("Sin permisos para definir metas.")
    formulario = MetaIndicadorForm(request.POST or None, usuario=request.user)
    if request.method == "POST" and formulario.is_valid():
        meta = formulario.save(commit=False)
        meta.full_clean()
        meta.save()
        messages.success(request, "Meta registrada correctamente.")
        return redirect("gestion:indicadores")
    return render(request, "gestion/indicadores/formulario_eva3.html", {"formulario": formulario, "titulo": "Registrar meta"})


@login_required
def editar_meta(request, pk):
    if not _puede_gestionar_meta(request.user):
        raise PermissionDenied("Sin permisos para editar metas.")
    meta = get_object_or_404(_metas_visibles(request.user), pk=pk)
    formulario = MetaIndicadorForm(request.POST or None, usuario=request.user, instance=meta)
    if request.method == "POST" and formulario.is_valid():
        valor = formulario.save(commit=False)
        valor.full_clean()
        valor.save()
        messages.success(request, "Meta actualizada correctamente.")
        return redirect("gestion:indicadores")
    return render(request, "gestion/indicadores/formulario_eva3.html", {"formulario": formulario, "titulo": "Editar meta"})


def _actividades_para_revisar(usuario):
    if es_admin(usuario):
        return Actividad.objects.all()
    if getattr(usuario, "rol", "") not in ("COORD", "DELEG", "VERIF"):
        raise PermissionDenied("Este perfil no puede validar actividades.")
    propio = usuario_funcionario(usuario)
    if propio is None:
        raise PermissionDenied("Necesita un funcionario asociado para revisar actividades.")
    return Actividad.objects.filter(delegacion_id=propio.delegacion_id).exclude(creado_por=usuario)


@login_required
def validar_evidencias(request):
    pendientes = _actividades_para_revisar(request.user).filter(
        estado__in=[Actividad.Estado.REGISTRADA, Actividad.Estado.EN_REVISION],
    ).select_related("delegacion", "funcionario")
    from django.core.paginator import Paginator
    pagina = Paginator(pendientes.order_by("fecha_actividad", "pk"), 25).get_page(request.GET.get("pagina"))
    # Listado de metas válidas por delegación y fecha; no se ofrecen de otros territorios.
    for actividad in pagina:
        actividad.metas_disponibles_eva3 = MetaIndicador.objects.filter(
            activo=True, delegacion_id=actividad.delegacion_id,
            periodo__fecha_inicio__lte=actividad.fecha_actividad,
            periodo__fecha_fin__gte=actividad.fecha_actividad,
        ).select_related("periodo").order_by("nombre")
        from .medicion_eva3_calculos import meta_aplica_a_actividad
        actividad.metas_disponibles_eva3 = [
            meta for meta in actividad.metas_disponibles_eva3
            if meta_aplica_a_actividad(meta, actividad)
        ]
    return render(request, "gestion/actividades/revisar_eva3.html", {"pagina": pagina})


@login_required
@require_POST
def resolver_actividad(request, pk):
    actividad = get_object_or_404(_actividades_para_revisar(request.user), pk=pk)
    if not _validadores_pueden_revisar(request.user, actividad):
        raise PermissionDenied("No puede revisar esta actividad.")
    if actividad.estado not in (Actividad.Estado.REGISTRADA, Actividad.Estado.EN_REVISION):
        raise PermissionDenied("La actividad ya fue revisada.")
    decision = request.POST.get("decision")
    if decision not in ("APR", "RECH"):
        raise PermissionDenied("Decisión inválida.")
    formulario = RevisionActividadConMetaForm(request.POST, actividad=actividad)
    if not formulario.is_valid():
        messages.error(request, "Seleccione un ítem de la misma delegación y período, o deje sin asignar.")
        return redirect("gestion:validar_evidencias")
    meta = formulario.cleaned_data["meta"] if decision == "APR" else None
    if meta:
        from .medicion_eva3_calculos import meta_aplica_a_actividad
        if not meta_aplica_a_actividad(meta, actividad):
            messages.error(request, "La meta no corresponde al funcionario de la actividad.")
            return redirect("gestion:validar_evidencias")
    # Una actividad debe estar terminada, tener contacto y no ser coordinación para contabilizar.
    with transaction.atomic():
        bloqueada = Actividad.objects.select_for_update().get(pk=actividad.pk)
        if bloqueada.estado not in (Actividad.Estado.REGISTRADA, Actividad.Estado.EN_REVISION):
            messages.error(request, "La actividad ya fue revisada por otra persona.")
            return redirect("gestion:validar_evidencias")
        bloqueada.estado = decision
        bloqueada.save(update_fields=["estado", "actualizado_en"])
        if meta:
            asignacion = ActividadIndicador(actividad=bloqueada, meta=meta, asignado_por=request.user)
            asignacion.full_clean()
            asignacion.save()
        ActividadRevision.objects.create(
            actividad=bloqueada, revisor=request.user, decision=decision,
            observacion=formulario.cleaned_data["observacion"],
        )
    messages.success(request, "Actividad revisada correctamente." + (" Si no cumple las reglas municipales, no sumará puntaje." if decision == "APR" else ""))
    return redirect("gestion:validar_evidencias")


def _resumen_informes(request):
    actividades = _filtrar_periodo_delegacion(actividades_visibles(request.user), request)
    # Forzar orden estable antes de pasar al CSV.
    actividades = actividades.select_related("delegacion", "funcionario", "creado_por").order_by("-fecha_actividad", "pk")
    filas = list(actividades)
    elegibles = sum(1 for a in filas if a.elegible_para_puntaje)
    return filas, elegibles


@login_required
def informes_gestion(request):
    filas, elegibles = _resumen_informes(request)
    total = len(filas)
    aprobadas = sum(1 for a in filas if a.estado == Actividad.Estado.APROBADA)
    metas_sgr = _metas_visibles(request.user).filter(activo=True)
    periodo_id = request.GET.get("periodo", "").strip()
    delegacion_id = request.GET.get("delegacion", "").strip()
    if periodo_id.isdecimal():
        metas_sgr = metas_sgr.filter(periodo_id=int(periodo_id))
    if delegacion_id.isdecimal():
        metas_sgr = metas_sgr.filter(delegacion_id=int(delegacion_id))
    resumenes_sgr = [_resumen_meta(meta) for meta in metas_sgr]

    delegaciones = {}
    for actividad in filas:
        clave = actividad.delegacion.nombre
        item = delegaciones.setdefault(clave, {"delegacion": clave, "total": 0, "aprobadas": 0, "elegibles": 0})
        item["total"] += 1
        item["aprobadas"] += actividad.estado == Actividad.Estado.APROBADA
        item["elegibles"] += actividad.elegible_para_puntaje
    return render(request, "gestion/informes/listar_eva3.html", {
        "filas": filas[:100], "total": total, "aprobadas": aprobadas,
        "elegibles": elegibles, "agrupados": list(delegaciones.values()),
        "resumenes_sgr": resumenes_sgr,
        "periodos": Periodo.objects.all(), "delegaciones": _delegaciones_usuario(request.user),
        "periodo_actual": request.GET.get("periodo", ""),
        "delegacion_actual": request.GET.get("delegacion", ""),
    })


@login_required
def exportar_informe_csv(request):
    filas, _ = _resumen_informes(request)
    respuesta = HttpResponse(content_type="text/csv; charset=utf-8")
    respuesta["Content-Disposition"] = 'attachment; filename="sgr_informe_actividades.csv"'
    respuesta.write("\ufeff")  # Excel reconoce UTF-8 en Windows.
    salida = csv.writer(respuesta, delimiter=";")
    def celda_segura(valor):
        texto = str(valor or "")
        if texto.lstrip().startswith(("=", "+", "-", "@")) or texto[:1] in ("\t", "\r", "\n"):
            return "'" + texto
        return texto
    salida.writerow(["Fecha", "Código", "Delegación", "Funcionario", "Actividad", "Estado", "Acción", "Solicitante", "Elegible para puntaje"])
    for a in filas:
        salida.writerow([celda_segura(v) for v in (
            a.fecha_actividad.isoformat(), a.codigo,
            a.delegacion.nombre, a.funcionario.nombre, a.titulo,
            a.get_estado_display(), a.get_tipo_accion_display(),
            a.nombre_solicitante, "Sí" if a.elegible_para_puntaje else "No",
        )])
    return respuesta
