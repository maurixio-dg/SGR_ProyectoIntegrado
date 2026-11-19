"""Control de alcance por delegación aplicado SIEMPRE en el servidor."""
from funcionarios.models import Funcionario
from .models import Vecino, Territorio, GestionSocial, CartaTubo


def es_admin(user):
    return bool(user.is_authenticated and (user.is_superuser or getattr(user, 'rol', '') == 'ADMIN'))


def funcionario_usuario(user):
    if not user.is_authenticated:
        return None
    return Funcionario.objects.filter(usuario=user).select_related('delegacion').first()


def delegacion_usuario(user):
    if es_admin(user):
        return None
    funcionario = funcionario_usuario(user)
    return funcionario.delegacion_id if funcionario else -1


def visibles(modelo, user):
    qs = modelo.objects.all()
    if es_admin(user):
        return qs
    delegacion_id = delegacion_usuario(user)
    return qs.filter(delegacion_id=delegacion_id) if delegacion_id != -1 else qs.none()


def puede_crear(user):
    if es_admin(user):
        return True
    return getattr(user, 'rol', '') not in ('CONS', 'VERIF') and funcionario_usuario(user) is not None


def puede_editar_gestion(user, gestion):
    return (gestion.estado != GestionSocial.Estado.APROBADA and
            (es_admin(user) or (gestion.creado_por_id == user.pk and delegacion_usuario(user) == gestion.delegacion_id)))


def puede_revisar(user, gestion):
    if gestion.estado in (GestionSocial.Estado.APROBADA, GestionSocial.Estado.RECHAZADA):
        return False
    if es_admin(user):
        return True
    return (getattr(user, 'rol', '') in ('COORD','DELEG','VERIF') and
            delegacion_usuario(user) == gestion.delegacion_id and gestion.creado_por_id != user.pk)


def puede_editar_carta(user, carta):
    return carta.estado != CartaTubo.Estado.CERRADA and (
        es_admin(user) or (carta.creado_por_id == user.pk and delegacion_usuario(user) == carta.delegacion_id))
