
from django.contrib import messages
from django.contrib.auth import get_user_model, update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm
from django import forms
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
import secrets
from django.views.decorators.cache import never_cache

from .forms import UsuarioCrearForm, UsuarioEditarForm


Usuario = get_user_model()


def _pagina_clave_temporal(request, usuario, clave):
    """Renderiza la clave exclusivamente en esta respuesta: no se guarda en sesión ni en logs."""
    respuesta = render(request, "usuarios/clave_temporal.html", {
        "usuario_creado": usuario,
        "clave_temporal": clave,
    })
    respuesta["Cache-Control"] = "no-store, no-cache, must-revalidate, private"
    respuesta["Pragma"] = "no-cache"
    return respuesta



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
@never_cache
def crear_usuario(request):

    formulario = UsuarioCrearForm(request.POST or None)

    if request.method == "POST" and formulario.is_valid():

        usuario = formulario.save(commit=False)

        # Los usuarios nuevos no reciben privilegios
        # especiales de Django.
        usuario.is_staff = False
        usuario.is_superuser = False
        usuario.debe_cambiar_password = True
        clave_temporal = secrets.token_urlsafe(18)
        usuario.set_password(clave_temporal)
        usuario.save()
        return _pagina_clave_temporal(request, usuario, clave_temporal)

    return render(
        request,
        "usuarios/formulario.html",
        {
            "formulario": formulario,
            "titulo": "Registrar usuario",
            "accion": "Registrar usuario",
            "es_creacion_temporal": True,
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



# ==========================================
# NUEVA CONTRASEÑA TEMPORAL POR ADMINISTRADOR
# ==========================================

@solo_administrador
@require_POST
@never_cache
def reiniciar_password_temporal(request, pk):
    usuario = get_object_or_404(Usuario, pk=pk, is_superuser=False)
    clave_temporal = secrets.token_urlsafe(18)
    usuario.set_password(clave_temporal)
    usuario.debe_cambiar_password = True
    usuario.save(update_fields=["password", "debe_cambiar_password"])
    return _pagina_clave_temporal(request, usuario, clave_temporal)


# ==========================================
# PERFIL PERSONAL (TODOS LOS USUARIOS)
# ==========================================

class PerfilForm(forms.ModelForm):

    class Meta:
        model = Usuario

        fields = ["first_name", "last_name", "email"]

        labels = {
            "first_name": "Nombre",
            "last_name": "Apellido",
            "email": "Correo electrónico",
        }

        widgets = {
            "first_name": forms.TextInput(
                attrs={"class": "form-control"}
            ),
            "last_name": forms.TextInput(
                attrs={"class": "form-control"}
            ),
            "email": forms.EmailInput(
                attrs={"class": "form-control"}
            ),
        }

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()

        existe = Usuario.objects.filter(
            email__iexact=email
        ).exclude(
            pk=self.instance.pk
        ).exists()

        if existe:
            raise forms.ValidationError(
                "Este correo electrónico ya pertenece a otra cuenta."
            )

        return email


@login_required
def mi_perfil(request):
    formulario = PerfilForm(request.POST or None, instance=request.user)
    if request.method == "POST" and formulario.is_valid():
        formulario.save()
        messages.success(request, "Tu perfil se actualizó correctamente.")
        return redirect("usuarios:mi_perfil")
    return render(request, "usuarios/mi_perfil.html", {"formulario": formulario})


@login_required
def cambiar_mi_password(request):
    formulario = PasswordChangeForm(request.user, request.POST or None)
    for campo in formulario.fields.values():
        campo.widget.attrs["class"] = "form-control"
    if request.method == "POST" and formulario.is_valid():
        usuario = formulario.save()
        era_obligatorio = usuario.debe_cambiar_password
        if era_obligatorio:
            usuario.debe_cambiar_password = False
            usuario.save(update_fields=["debe_cambiar_password"])
        update_session_auth_hash(request, usuario)
        messages.success(request, "Contraseña actualizada correctamente.")
        return redirect("gestion:dashboard" if era_obligatorio else "usuarios:mi_perfil")
    return render(request, "usuarios/cambiar_password.html", {
        "formulario": formulario,
        "cambio_obligatorio": request.user.debe_cambiar_password,
    })
