"""Evita acceder al SGR hasta cambiar una contraseña temporal."""

from django.conf import settings
from django.shortcuts import redirect


class CambioPasswordInicialMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        usuario = getattr(request, "user", None)
        if usuario and usuario.is_authenticated and not usuario.is_superuser:
            if getattr(usuario, "debe_cambiar_password", False):
                ruta = request.path_info
                permitidas = (
                    "/usuarios/mi-perfil/contrasena/",
                    "/logout/",
                    "/static/",
                )
                static_url = settings.STATIC_URL
                if static_url.startswith("/"):
                    permitidas += (static_url,)
                if not any(ruta.startswith(p) for p in permitidas):
                    return redirect("usuarios:cambiar_mi_password")
        return self.get_response(request)
