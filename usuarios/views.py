
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.shortcuts import (
    render,
    redirect,
    get_object_or_404,
)
from django.views.decorators.http import require_POST

from functools import wraps

from .forms import UsuarioCrearForm, UsuarioEditarForm


Usuario = get_user_model()


# ==========================================
# CONTROL DE ACCESO
# ==========================================

def solo_administrador(vista):
    @wraps(vista)
    @login_required
    def protegida(request, *args, **kwargs):

        if not request.user.is_superuser:
            raise PermissionDenied(
                "Solo el superadministrador puede gestionar cuentas."
            )

        return vista(request, *args, **kwargs)

    return protegida


# ==========================================
# LISTAR USUARIOS
# ==========================================

@solo_administrador
def listar_usuarios(request):

    buscar = request.GET.get("buscar", "").strip()
    rol = request.GET.get("rol", "").strip()

    usuarios = Usuario.objects.all().order_by("username")

    if buscar:
        usuarios = usuarios.filter(
            Q(username__icontains=buscar)
            | Q(first_name__icontains=buscar)
            | Q(last_name__icontains=buscar)
            | Q(email__icontains=buscar)
        )

    roles_validos = [
        valor for valor, etiqueta in Usuario.Rol.choices
    ]

    if rol in roles_validos:
        usuarios = usuarios.filter(rol=rol)

    contexto = {
        "usuarios": usuarios,
        "buscar": buscar,
        "rol": rol,
        "roles": Usuario.Rol.choices,
        "total": usuarios.count(),
    }

    return render(
        request,
        "usuarios/listar.html",
        contexto
    )


# ==========================================
# CREAR USUARIO
# ==========================================

@solo_administrador
def crear_usuario(request):

    formulario = UsuarioCrearForm(request.POST or None)

    if request.method == "POST" and formulario.is_valid():

        usuario = formulario.save(commit=False)

        # Los usuarios nuevos no reciben privilegios
        # especiales de Django.
        usuario.is_staff = False
        usuario.is_superuser = False

        usuario.save()

        messages.success(
            request,
            "Usuario registrado correctamente."
        )

        return redirect("usuarios:listar")

    return render(
        request,
        "usuarios/formulario.html",
        {
            "formulario": formulario,
            "titulo": "Registrar usuario",
            "accion": "Registrar usuario",
        }
    )


# ==========================================
# EDITAR USUARIO
# ==========================================

@solo_administrador
def editar_usuario(request, pk):

    usuario = get_object_or_404(
        Usuario,
        pk=pk
    )

    if usuario.is_superuser:
        messages.error(
            request,
            "Las cuentas de superadministrador "
            "se gestionan por separado."
        )
        return redirect("usuarios:listar")

    formulario = UsuarioEditarForm(
        request.POST or None,
        instance=usuario
    )

    if request.method == "POST" and formulario.is_valid():

        usuario = formulario.save(commit=False)

        # Impedir que se otorguen privilegios
        # internos de Django.
        usuario.is_staff = False
        usuario.is_superuser = False

        usuario.save()

        messages.success(
            request,
            "Usuario actualizado correctamente."
        )

        return redirect("usuarios:listar")

    return render(
        request,
        "usuarios/formulario.html",
        {
            "formulario": formulario,
            "titulo": "Editar usuario",
            "accion": "Guardar cambios",
        }
    )


# ==========================================
# DESACTIVAR USUARIO
# ==========================================

@solo_administrador
@require_POST
def desactivar_usuario(request, pk):

    usuario = get_object_or_404(
        Usuario,
        pk=pk
    )

    if usuario.is_superuser:
        messages.error(
            request,
            "No se puede desactivar una cuenta "
            "de superadministrador desde este módulo."
        )
        return redirect("usuarios:listar")

    if usuario.pk == request.user.pk:
        messages.error(
            request,
            "No puede desactivar su propia cuenta."
        )
        return redirect("usuarios:listar")

    usuario.is_active = False
    usuario.save(update_fields=["is_active"])

    messages.success(
        request,
        "Usuario desactivado correctamente."
    )

    return redirect("usuarios:listar")


# ==========================================
# REACTIVAR USUARIO
# ==========================================

@solo_administrador
@require_POST
def activar_usuario(request, pk):

    usuario = get_object_or_404(
        Usuario,
        pk=pk
    )

    if usuario.is_superuser:
        messages.error(
            request,
            "Las cuentas de superadministrador "
            "se gestionan por separado."
        )
        return redirect("usuarios:listar")

    usuario.is_active = True
    usuario.save(update_fields=["is_active"])

    messages.success(
        request,
        "Usuario activado correctamente."
    )

    return redirect("usuarios:listar")
