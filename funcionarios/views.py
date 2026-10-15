
from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Q, ProtectedError
from django.shortcuts import (
    render,
    redirect,
    get_object_or_404,
)

from .models import Funcionario
from .forms import FuncionarioForm


def solo_administrador(vista):
    @wraps(vista)
    @login_required
    def protegida(request, *args, **kwargs):

        usuario = request.user

        if not (
            usuario.is_superuser
            or getattr(usuario, "rol", None) == "ADMIN"
        ):
            raise PermissionDenied(
                "No tiene permisos para gestionar funcionarios."
            )

        return vista(request, *args, **kwargs)

    return protegida


@solo_administrador
def listar_funcionarios(request):

    buscar = request.GET.get("buscar", "").strip()
    delegacion_id = request.GET.get("delegacion", "").strip()

    funcionarios = Funcionario.objects.select_related(
        "delegacion",
        "cargo",
        "usuario"
    ).all()

    if buscar:
        funcionarios = funcionarios.filter(
            Q(nombre__icontains=buscar)
            | Q(rut__icontains=buscar)
            | Q(email__icontains=buscar)
        )

    if delegacion_id.isdigit():
        funcionarios = funcionarios.filter(
            delegacion_id=int(delegacion_id)
        )

    from delegaciones.models import Delegacion

    contexto = {
        "funcionarios": funcionarios,
        "delegaciones": Delegacion.objects.all(),
        "buscar": buscar,
        "delegacion_seleccionada": delegacion_id,
        "total": funcionarios.count(),
    }

    return render(
        request,
        "funcionarios/listar.html",
        contexto
    )


@solo_administrador
def crear_funcionario(request):

    formulario = FuncionarioForm(request.POST or None)

    if request.method == "POST" and formulario.is_valid():
        formulario.save()

        messages.success(
            request,
            "Funcionario registrado correctamente."
        )

        return redirect("funcionarios:listar")

    return render(
        request,
        "funcionarios/formulario.html",
        {
            "formulario": formulario,
            "titulo": "Registrar funcionario",
            "accion": "Registrar funcionario",
        }
    )


@solo_administrador
def editar_funcionario(request, pk):

    funcionario = get_object_or_404(
        Funcionario,
        pk=pk
    )

    formulario = FuncionarioForm(
        request.POST or None,
        instance=funcionario
    )

    if request.method == "POST" and formulario.is_valid():
        formulario.save()

        messages.success(
            request,
            "Funcionario actualizado correctamente."
        )

        return redirect("funcionarios:listar")

    return render(
        request,
        "funcionarios/formulario.html",
        {
            "formulario": formulario,
            "titulo": "Editar funcionario",
            "accion": "Guardar cambios",
        }
    )


@solo_administrador
def eliminar_funcionario(request, pk):

    funcionario = get_object_or_404(
        Funcionario,
        pk=pk
    )

    if request.method == "POST":
        try:
            funcionario.delete()

            messages.success(
                request,
                "Funcionario eliminado correctamente."
            )

        except ProtectedError:
            messages.error(
                request,
                "No se puede eliminar este funcionario "
                "porque tiene registros asociados."
            )

        return redirect("funcionarios:listar")

    return render(
        request,
        "funcionarios/confirmar_eliminar.html",
        {"funcionario": funcionario}
    )
