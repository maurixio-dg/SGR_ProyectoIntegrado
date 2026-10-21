
from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views


urlpatterns = [
    # Administración interna
    path("admin/", admin.site.urls),

    # Inicio de sesión
    path(
        "login/",
        auth_views.LoginView.as_view(
            template_name="login.html",
            redirect_authenticated_user=True
        ),
        name="login"
    ),

    # Cierre de sesión
    path(
        "logout/",
        auth_views.LogoutView.as_view(),
        name="logout"
    ),

    # Recuperación de contraseña
    path(
        "recuperar-password/",
        auth_views.PasswordResetView.as_view(
            template_name="registration/password_reset_form.html",
            email_template_name="registration/password_reset_email.html",
            subject_template_name="registration/password_reset_subject.txt",
            success_url="/recuperar-password/enviado/"
        ),
        name="password_reset"
    ),

    path(
        "recuperar-password/enviado/",
        auth_views.PasswordResetDoneView.as_view(
            template_name="registration/password_reset_done.html"
        ),
        name="password_reset_done"
    ),

    path(
        "restablecer-password/<uidb64>/<token>/",
        auth_views.PasswordResetConfirmView.as_view(
            template_name="registration/password_reset_confirm.html",
            success_url="/restablecer-password/completado/"
        ),
        name="password_reset_confirm"
    ),

    path(
        "restablecer-password/completado/",
        auth_views.PasswordResetCompleteView.as_view(
            template_name="registration/password_reset_complete.html"
        ),
        name="password_reset_complete"
    ),

    # Módulos municipales
    path("delegaciones/", include("delegaciones.urls")),
    path("catalogos/", include("catalogos.urls")),
    path("funcionarios/", include("funcionarios.urls")),

    # Panel principal
    path("", include("gestion.urls")),

    # Gestión de usuarios
    path("usuarios/", include("usuarios.urls")),
]
