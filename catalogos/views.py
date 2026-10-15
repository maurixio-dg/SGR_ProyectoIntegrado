
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
from django.views.decorators.http import require_POST

from .forms import CargoForm, FuncionForm
from .models import Cargo, Funcion


# ==========================================
# CONTROL DE ACCESO
# ==========================================

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
                "No tiene permisos para administrar catálogos."
            )

        return vista(request, *args, **kwargs)

    return protegida


# ==========================================
# CRUD DE CARGOS
# ==========================================

@solo_administrador
def listar_cargos(request):
    buscar = request.GET.get("buscar", "").strip()

    cargos = Cargo.objects.all()

    if buscar:
        cargos = cargos.filter(
            nombre_cargo__icontains=buscar
        )

    contexto = {
        "cargos": cargos,
        "buscar": buscar,
        "total": cargos.count(),
    }

    return render(
        request,
        "catalogos/cargos/listar.html",
        contexto
    )


@solo_administrador
def crear_cargo(request):
    formulario = CargoForm(request.POST or None)

    if request.method == "POST" and formulario.is_valid():
        formulario.save()

        messages.success(
            request,
            "Cargo registrado correctamente."
        )

        return redirect("catalogos:listar_cargos")

    return render(
        request,
        "catalogos/cargos/formulario.html",
        {
            "formulario": formulario,
            "titulo": "Registrar cargo",
            "accion": "Registrar cargo",
        }
    )


@solo_administrador
def editar_cargo(request, pk):
    cargo = get_object_or_404(Cargo, pk=pk)

    formulario = CargoForm(
        request.POST or None,
        instance=cargo
    )

    if request.method == "POST" and formulario.is_valid():
        formulario.save()

        messages.success(
            request,
            "Cargo actualizado correctamente."
        )

        return redirect("catalogos:listar_cargos")

    return render(
        request,
        "catalogos/cargos/formulario.html",
        {
            "formulario": formulario,
            "titulo": "Editar cargo",
            "accion": "Guardar cambios",
        }
    )


@solo_administrador
def eliminar_cargo(request, pk):
    cargo = get_object_or_404(Cargo, pk=pk)

    if request.method == "POST":
        try:
            cargo.delete()

            messages.success(
                request,
                "Cargo eliminado correctamente."
            )

        except ProtectedError:
            messages.error(
                request,
                "No se puede eliminar el cargo porque "
                "tiene funcionarios o funciones asociados."
            )

        return redirect("catalogos:listar_cargos")

    return render(
        request,
        "catalogos/cargos/confirmar_eliminar.html",
        {"cargo": cargo}
    )


# ==========================================
# CRUD DE FUNCIONES POR CARGO
# ==========================================

@solo_administrador
def listar_funciones(request):
    buscar = request.GET.get("buscar", "").strip()
    cargo_id = request.GET.get("cargo", "").strip()

    funciones = Funcion.objects.select_related(
        "cargo"
    ).all()

    if buscar:
        funciones = funciones.filter(
            Q(nombre__icontains=buscar)
            | Q(descripcion__icontains=buscar)
            | Q(cargo__nombre_cargo__icontains=buscar)
        )

    if cargo_id.isdigit():
        funciones = funciones.filter(
            cargo_id=int(cargo_id)
        )

    contexto = {
        "funciones": funciones,
        "cargos": Cargo.objects.all(),
        "buscar": buscar,
        "cargo_seleccionado": cargo_id,
        "total": funciones.count(),
    }

    return render(
        request,
        "catalogos/funciones/listar.html",
        contexto
    )


@solo_administrador
def crear_funcion(request):
    formulario = FuncionForm(request.POST or None)

    if request.method == "POST" and formulario.is_valid():
        formulario.save()

        messages.success(
            request,
            "Función registrada correctamente."
        )

        return redirect("catalogos:listar_funciones")

    return render(
        request,
        "catalogos/funciones/formulario.html",
        {
            "formulario": formulario,
            "titulo": "Registrar función",
            "accion": "Registrar función",
        }
    )


@solo_administrador
def editar_funcion(request, pk):
    funcion = get_object_or_404(Funcion, pk=pk)

    formulario = FuncionForm(
        request.POST or None,
        instance=funcion
    )

    if request.method == "POST" and formulario.is_valid():
        formulario.save()

        messages.success(
            request,
            "Función actualizada correctamente."
        )

        return redirect("catalogos:listar_funciones")

    return render(
        request,
        "catalogos/funciones/formulario.html",
        {
            "formulario": formulario,
            "titulo": "Editar función",
            "accion": "Guardar cambios",
        }
    )


# ==========================================
# ACTIVAR / DESACTIVAR FUNCIONES
# ==========================================

@solo_administrador
@require_POST
def cambiar_estado_funcion(request, pk):
    funcion = get_object_or_404(Funcion, pk=pk)

    funcion.estado = not funcion.estado
    funcion.save(update_fields=["estado"])

    if funcion.estado:
        messages.success(
            request,
            "Función activada correctamente."
        )
    else:
        messages.success(
            request,
            "Función desactivada correctamente."
        )

    return redirect("catalogos:listar_funciones")
