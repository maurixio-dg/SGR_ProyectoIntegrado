from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Q
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.core.paginator import Paginator
from django.views.decorators.http import require_safe
from funcionarios.models import Funcionario
from .models import Actividad
from .actividades_eva3_forms import ActividadForm


def es_admin(usuario):
    return usuario.is_superuser or getattr(usuario, "rol", "") == "ADMIN"


def actividades_visibles(usuario):
    consulta = Actividad.objects.select_related("funcionario", "delegacion", "periodo", "creado_por")
    if es_admin(usuario):
        return consulta
    funcionario = Funcionario.objects.filter(usuario=usuario).first()
    if funcionario is None:
        return consulta.none()
    if getattr(usuario, "rol", "") in ("COORD", "DELEG"):
        return consulta.filter(delegacion_id=funcionario.delegacion_id)
    return consulta.filter(funcionario=funcionario)


def puede_registrar(usuario):
    if es_admin(usuario):
        return True
    if getattr(usuario, "rol", "") in ("CONS", "VERIF"):
        return False
    return Funcionario.objects.filter(usuario=usuario).exists()


@login_required
def listar_actividades(request):
    actividades = actividades_visibles(request.user)
    buscar = request.GET.get("buscar", "").strip()
    estado = request.GET.get("estado", "").strip()
    if buscar:
        actividades = actividades.filter(
            Q(titulo__icontains=buscar)
            | Q(nombre_solicitante__icontains=buscar)
            | Q(funcionario__nombre__icontains=buscar)
        )
    estados = dict(Actividad.Estado.choices)
    if estado in estados:
        actividades = actividades.filter(estado=estado)
    pagina = Paginator(actividades, 20).get_page(request.GET.get("pagina"))
    # Evitar enlaces que deriven en 403: el alcance sigue definido por actividades_visibles.
    funcionario_usuario = Funcionario.objects.filter(usuario=request.user).first()
    admin_actual = es_admin(request.user)
    pagina.object_list = list(pagina.object_list)
    for item in pagina.object_list:
        item.puede_editar_eva3 = (
            item.estado != Actividad.Estado.APROBADA
            and (admin_actual or bool(funcionario_usuario and item.funcionario_id == funcionario_usuario.pk))
        )
    return render(request, "gestion/actividades/listar_eva3.html", {
        "pagina": pagina, "buscar": buscar, "estado": estado,
        "estados": Actividad.Estado.choices, "puede_registrar": puede_registrar(request.user),
    })


@login_required
def registrar_actividad(request):
    if not puede_registrar(request.user):
        raise PermissionDenied("No tiene un funcionario asociado o permisos para registrar actividades.")
    formulario = ActividadForm(
        request.POST or None, request.FILES or None, usuario=request.user,
    )
    if request.method == "POST" and formulario.is_valid():
        with transaction.atomic():
            # Serializa registros del mismo funcionario para respetar el máximo diario.
            Funcionario.objects.select_for_update().get(pk=formulario.cleaned_data["funcionario"].pk)
            actividad = formulario.save(commit=False)
            actividad.creado_por = request.user
            actividad.full_clean()
            actividad.save()
        messages.success(request, "Actividad registrada correctamente.")
        return redirect("gestion:listar_actividades")
    return render(request, "gestion/actividades/formulario_eva3.html", {
        "formulario": formulario, "titulo": "Registrar actividad",
    })


@login_required
def editar_actividad(request, pk):
    actividad = get_object_or_404(actividades_visibles(request.user), pk=pk)
    funcionario = Funcionario.objects.filter(usuario=request.user).first()
    if request.method in ("GET", "HEAD") and (
        actividad.estado == Actividad.Estado.APROBADA
        or not (es_admin(request.user) or (funcionario and actividad.funcionario_id == funcionario.pk))
    ):
        return redirect("gestion:detalle_actividad", pk=actividad.pk)
    if not (es_admin(request.user) or (funcionario and actividad.funcionario_id == funcionario.pk)):
        raise PermissionDenied("Solo el responsable o un administrador puede editar este registro.")
    if actividad.estado == Actividad.Estado.APROBADA:
        raise PermissionDenied("Una actividad aprobada no puede modificarse directamente.")
    formulario = ActividadForm(
        request.POST or None, request.FILES or None,
        instance=actividad, usuario=request.user,
    )
    if request.method == "POST" and formulario.is_valid():
        with transaction.atomic():
            Funcionario.objects.select_for_update().get(pk=formulario.cleaned_data["funcionario"].pk)
            actualizado = formulario.save(commit=False)
            actualizado.full_clean()
            actualizado.save()
        messages.success(request, "Actividad actualizada correctamente.")
        return redirect("gestion:listar_actividades")
    return render(request, "gestion/actividades/formulario_eva3.html", {
        "formulario": formulario, "titulo": "Editar actividad",
    })


@login_required
@require_safe
def detalle_actividad(request, pk):
    actividad = get_object_or_404(actividades_visibles(request.user), pk=pk)
    from .models import ActividadIndicador
    asignacion = (ActividadIndicador.objects.select_related("meta")
                  .filter(actividad_id=actividad.pk).first())
    revision = actividad.revisiones_eva3.select_related("revisor").first()
    funcionario = Funcionario.objects.filter(usuario=request.user).first()
    puede_editar = (
        actividad.estado != Actividad.Estado.APROBADA
        and (es_admin(request.user) or bool(funcionario and actividad.funcionario_id == funcionario.pk))
    )
    return render(request, "gestion/actividades/detalle_eva3.html", {
        "actividad": actividad,
        "asignacion": asignacion,
        "revision": revision,
        "puede_editar": puede_editar,
    })


@login_required
def descargar_evidencia(request, pk):
    actividad = get_object_or_404(actividades_visibles(request.user), pk=pk)
    if not actividad.evidencia:
        raise Http404("No existe evidencia adjunta.")
    archivo = actividad.evidencia.open("rb")
    return FileResponse(archivo, as_attachment=True, filename=actividad.evidencia.name.split("/")[-1])
