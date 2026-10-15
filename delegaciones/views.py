
from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import ProtectedError, Q
from django.shortcuts import (
    render,
    redirect,
    get_object_or_404,
)

from .forms import DelegacionForm
from .models import Delegacion


def solo_administrador(vista):
    @wraps(vista)
    @login_required
    def protegida(request, *args, **kwargs):
        usuario = request.user

        autorizado = (
            usuario.is_superuser
            or getattr(usuario, "rol", None) == "ADMIN"
        )

        if not autorizado:
            raise PermissionDenied(
                "No tiene permisos para administrar delegaciones."
            )

        return vista(request, *args, **kwargs)

    return protegida


@solo_administrador
def listar_delegaciones(request):
    buscar = request.GET.get("buscar", "").strip()
    estado = request.GET.get("estado", "")

    delegaciones = Delegacion.objects.all()

    if buscar:
        delegaciones = delegaciones.filter(
            nombre__icontains=buscar
        )

    if estado == "activa":
        delegaciones = delegaciones.filter(estado=True)

    elif estado == "inactiva":
        delegaciones = delegaciones.filter(estado=False)

    contexto = {
        "delegaciones": delegaciones,
        "buscar": buscar,
        "estado": estado,
        "total": delegaciones.count(),
    }

    return render(
        request,
        "delegaciones/listar.html",
        contexto
    )


@solo_administrador
def crear_delegacion(request):
    formulario = DelegacionForm(
        request.POST or None
    )

    if request.method == "POST" and formulario.is_valid():
        formulario.save()

        messages.success(
            request,
            "Delegación registrada correctamente."
        )

        return redirect("delegaciones:listar")

    return render(
        request,
        "delegaciones/formulario.html",
        {
            "formulario": formulario,
            "titulo": "Registrar delegación",
            "accion": "Registrar delegación",
        }
    )


@solo_administrador
def editar_delegacion(request, pk):
    delegacion = get_object_or_404(
        Delegacion,
        pk=pk
    )

    formulario = DelegacionForm(
        request.POST or None,
        instance=delegacion
    )

    if request.method == "POST" and formulario.is_valid():
        formulario.save()

        messages.success(
            request,
            "Delegación actualizada correctamente."
        )

        return redirect("delegaciones:listar")

    return render(
        request,
        "delegaciones/formulario.html",
        {
            "formulario": formulario,
            "titulo": "Editar delegación",
            "accion": "Guardar cambios",
        }
    )


@solo_administrador
def eliminar_delegacion(request, pk):
    delegacion = get_object_or_404(
        Delegacion,
        pk=pk
    )

    if request.method == "POST":
        try:
            delegacion.delete()

            messages.success(
                request,
                "Delegación eliminada correctamente."
            )

        except ProtectedError:
            messages.error(
                request,
                "No se puede eliminar esta delegación "
                "porque tiene funcionarios asociados. "
                "Puede desactivarla desde Editar."
            )

        return redirect("delegaciones:listar")

    return render(
        request,
        "delegaciones/confirmar_eliminar.html",
        {"delegacion": delegacion}
    )
