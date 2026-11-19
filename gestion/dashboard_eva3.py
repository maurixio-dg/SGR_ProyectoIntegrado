"""Resumen real del panel SGR (Fases 1-3). No modifica la base de datos."""
from decimal import Decimal, ROUND_HALF_UP

from catalogos.models import Cargo
from delegaciones.models import Delegacion
from funcionarios.models import Funcionario

from .actividades_eva3 import actividades_visibles, es_admin
from .operativa_eva3 import _agenda_visibles, _metas_visibles
from .operativa_eva3_forms import es_jefatura, usuario_funcionario
from .medicion_eva3_calculos import calcular_resumen_meta
from .models import Actividad


def _resumen_tablas_maestras(usuario):
    """Un perfil no administrador no ve cifras globales de otras delegaciones."""
    if es_admin(usuario):
        return {
            "total_delegaciones": Delegacion.objects.count(),
            "total_funcionarios": Funcionario.objects.count(),
            "total_cargos": Cargo.objects.count(),
        }

    propio = usuario_funcionario(usuario)
    if propio is None:
        return {"total_delegaciones": 0, "total_funcionarios": 0, "total_cargos": 0}

    if es_jefatura(usuario) or getattr(usuario, "rol", "") in ("VERIF", "CONS"):
        funcionarios = Funcionario.objects.filter(delegacion_id=propio.delegacion_id)
    else:
        funcionarios = Funcionario.objects.filter(pk=propio.pk)

    return {
        "total_delegaciones": 1,
        "total_funcionarios": funcionarios.count(),
        "total_cargos": funcionarios.values("cargo_id").distinct().count(),
    }


def obtener_contexto_dashboard(usuario):
    """Consulta registros visibles para el usuario; sin valores de demostración."""
    contexto = _resumen_tablas_maestras(usuario)

    actividades = actividades_visibles(usuario)
    compromisos = _agenda_visibles(usuario)
    metas = _metas_visibles(usuario).filter(activo=True)

    contexto.update({
        "total_actividades": actividades.count(),
        "total_aprobadas": actividades.filter(estado=Actividad.Estado.APROBADA).count(),
        "total_compromisos": compromisos.count(),
        "total_indicadores": metas.count(),
        "actividades_recientes": list(
            actividades.order_by("-fecha_actividad", "-creado_en", "-pk")[:5]
        ),
        "hay_metas": False,
        "cumplimiento_metas": None,
    })

    # Promedio ponderado de las metas activas visibles. Se normaliza por la
    # suma de ponderadores (no se suman porcentajes de distintas delegaciones).
    total_ponderadores = Decimal("0")
    suma_ponderada = Decimal("0")
    suma_porcentajes = Decimal("0")
    numero_metas = 0

    for meta in metas:
        resumen = calcular_resumen_meta(meta)
        porcentaje = resumen["porcentaje"]
        ponderador = meta.ponderacion
        total_ponderadores += ponderador
        suma_ponderada += porcentaje * ponderador
        suma_porcentajes += porcentaje
        numero_metas += 1

    if numero_metas:
        promedio = (
            suma_ponderada / total_ponderadores
            if total_ponderadores > 0
            else suma_porcentajes / Decimal(numero_metas)
        )
        contexto["hay_metas"] = True
        contexto["cumplimiento_metas"] = promedio.quantize(
            Decimal("0.1"), rounding=ROUND_HALF_UP
        )

    return contexto
