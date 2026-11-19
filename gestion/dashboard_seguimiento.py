"""Panel de seguimiento con agregados reales, siempre dentro del ámbito del usuario.

No genera nuevas tablas ni modifica resultados; solo consulta los modelos SGR.
"""
from datetime import date
from decimal import Decimal

from django.db.models import Count, Q
from django.db.models.functions import TruncMonth
from django.utils import timezone

from delegaciones.models import Delegacion
from funcionarios.models import Funcionario
from .actividades_eva3 import actividades_visibles, es_admin
from .medicion_eva3_calculos import calcular_resumen_meta
from .models import Actividad, AgendaCompromiso, Periodo
from .operativa_eva3 import _agenda_visibles, _metas_visibles
from .operativa_eva3_forms import es_jefatura, usuario_funcionario

MESES = ("ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic")


def _id_seguro(valor):
    """Descarta valores maliciosos/extraños antes de filtrar; jamás amplía el queryset."""
    valor = str(valor or "")
    return int(valor) if valor.isascii() and valor.isdecimal() and len(valor) < 10 else None


def _primero_mes(momento):
    return date(momento.year, momento.month, 1)


def _mes_anterior(momento):
    return date(momento.year - 1, 12, 1) if momento.month == 1 else date(momento.year, momento.month - 1, 1)


def _lista_meses(fin, cantidad=6):
    fechas = [_primero_mes(fin)]
    for _ in range(cantidad-1):
        fechas.append(_mes_anterior(fechas[-1]))
    return list(reversed(fechas))


def _aplicar_rango(actividades, agenda, metas, periodo):
    if periodo:
        actividades = actividades.filter(fecha_actividad__range=(periodo.fecha_inicio, periodo.fecha_fin))
        agenda = agenda.filter(fecha__range=(periodo.fecha_inicio, periodo.fecha_fin))
        metas = metas.filter(periodo_id=periodo.pk)
    return actividades, agenda, metas


def obtener_panel_seguimiento(usuario, parametros):
    """Las opciones de los filtros se limitan al mismo ámbito de actividades visibles.

    El usuario jamás puede ampliar su acceso mediante identificadores GET manipulados.
    """
    administrador = es_admin(usuario)
    jefatura = es_jefatura(usuario)
    funcionario_actual = usuario_funcionario(usuario)
    puede_filtrar_personal = administrador or jefatura

    if administrador:
        delegaciones = Delegacion.objects.order_by("nombre")
        funcionarios = Funcionario.objects.select_related("delegacion").order_by("nombre")
        titulo_ambito = "Gestión municipal"
    elif funcionario_actual:
        delegaciones = Delegacion.objects.filter(pk=funcionario_actual.delegacion_id)
        funcionarios = Funcionario.objects.filter(delegacion_id=funcionario_actual.delegacion_id).order_by("nombre") if jefatura else Funcionario.objects.filter(pk=funcionario_actual.pk)
        titulo_ambito = "Mi delegación" if jefatura else "Mi gestión"
    else:
        delegaciones = Delegacion.objects.none()
        funcionarios = Funcionario.objects.none()
        titulo_ambito = "Sin funcionario asociado"

    actividades = actividades_visibles(usuario)
    agenda = _agenda_visibles(usuario)
    metas = _metas_visibles(usuario).filter(activo=True)

    delegacion_solicitada = _id_seguro(parametros.get("delegacion")) if administrador else None
    seleccion_delegacion = delegacion_solicitada if delegacion_solicitada and delegaciones.filter(pk=delegacion_solicitada).exists() else None
    if seleccion_delegacion:
        actividades = actividades.filter(delegacion_id=seleccion_delegacion)
        agenda = agenda.filter(delegacion_id=seleccion_delegacion)
        metas = metas.filter(delegacion_id=seleccion_delegacion)
        funcionarios = funcionarios.filter(delegacion_id=seleccion_delegacion)

    funcionario_solicitado = _id_seguro(parametros.get("funcionario")) if puede_filtrar_personal else None
    seleccion_funcionario = funcionario_solicitado if funcionario_solicitado and funcionarios.filter(pk=funcionario_solicitado).exists() else None
    if seleccion_funcionario:
        actividades = actividades.filter(funcionario_id=seleccion_funcionario)
        agenda = agenda.filter(responsable_id=seleccion_funcionario)
        # Una meta colectiva no debe aparentar ser una meta individual.
        metas = metas.filter(configuracion_sgr__funcionario_id=seleccion_funcionario)
    elif not puede_filtrar_personal and funcionario_actual:
        # Mis metas: solo las efectivamente asignadas a mi persona.
        metas = metas.filter(configuracion_sgr__funcionario_id=funcionario_actual.pk)

    periodo_solicitado = _id_seguro(parametros.get("periodo"))
    periodo = Periodo.objects.filter(pk=periodo_solicitado).first() if periodo_solicitado else None
    actividades, agenda, metas = _aplicar_rango(actividades, agenda, metas, periodo)

    conteo_estados = dict(actividades.values_list("estado").annotate(total=Count("pk")))
    total_actividades = sum(conteo_estados.values())
    estados = []
    for codigo, nombre in Actividad.Estado.choices:
        cuenta = conteo_estados.get(codigo, 0)
        porcentaje = round(cuenta * 100 / total_actividades) if total_actividades else 0
        estados.append({"codigo": codigo, "nombre": nombre, "total": cuenta, "porcentaje": porcentaje})

    conteo_agenda = dict(agenda.values_list("estado").annotate(total=Count("pk")))
    total_agenda = sum(conteo_agenda.values())
    estados_agenda = [
        {"nombre": nombre, "total": conteo_agenda.get(codigo, 0),
         "porcentaje": round(100 * conteo_agenda.get(codigo, 0) / total_agenda) if total_agenda else 0}
        for codigo, nombre in AgendaCompromiso.Estado.choices
    ]

    fin_trend = timezone.localdate()
    if periodo:
        fin_trend = min(max(fin_trend, periodo.fecha_inicio), periodo.fecha_fin)
    meses = _lista_meses(fin_trend)
    actividad_mensual = actividades.filter(fecha_actividad__gte=meses[0]).annotate(
        mes=TruncMonth("fecha_actividad")
    ).values("mes").annotate(total=Count("pk")).order_by("mes")
    por_mes = {(item["mes"].year, item["mes"].month): item["total"] for item in actividad_mensual if item["mes"]}
    max_mes = max([por_mes.get((mes.year, mes.month), 0) for mes in meses] + [1])
    tendencia = [
        {"etiqueta": f"{MESES[mes.month - 1]} {str(mes.year)[2:]}",
         "total": por_mes.get((mes.year, mes.month), 0),
         "altura": round(100 * por_mes.get((mes.year, mes.month), 0) / max_mes)}
        for mes in meses
    ]

    if administrador and not seleccion_delegacion:
        etiqueta_comparativa = "Actividad por delegación"
        comparativa_base = actividades.values("delegacion_id", "delegacion__nombre").annotate(
            total=Count("pk"), aprobadas=Count("pk", filter=Q(estado=Actividad.Estado.APROBADA))
        ).order_by("-total", "delegacion__nombre")[:8]
        comparativa = [{"nombre": v["delegacion__nombre"], "total": v["total"],
                        "aprobadas": v["aprobadas"]} for v in comparativa_base]
    elif puede_filtrar_personal and not seleccion_funcionario:
        etiqueta_comparativa = "Carga por funcionario"
        comparativa_base = actividades.values("funcionario_id", "funcionario__nombre").annotate(
            total=Count("pk"), aprobadas=Count("pk", filter=Q(estado=Actividad.Estado.APROBADA))
        ).order_by("-total", "funcionario__nombre")[:8]
        comparativa = [{"nombre": v["funcionario__nombre"], "total": v["total"],
                        "aprobadas": v["aprobadas"]} for v in comparativa_base]
    else:
        etiqueta_comparativa = "Actividad visible"
        comparativa = [{"nombre": "Mis actividades" if not administrador else "Actividades",
                        "total": total_actividades, "aprobadas": conteo_estados.get(Actividad.Estado.APROBADA, 0)}]
    max_comparativa = max([f["total"] for f in comparativa] + [1])
    for fila in comparativa:
        fila["porcentaje"] = round(100 * fila["total"] / max_comparativa)

    metas_totales = metas.count()
    semaforos = []
    for meta in metas.select_related("periodo").order_by("nombre", "pk")[:6]:
        resumen = calcular_resumen_meta(meta)
        semaforos.append({"nombre": meta.nombre, "porcentaje": resumen["porcentaje"],
                          "ancho": max(0, min(100, round(resumen["porcentaje"]))),
                          "estado": resumen["semaforo"], "cantidad": resumen["cantidad"],
                          "meta_ajustada": resumen["meta_ajustada"]})

    return {
        "panel_ambito": titulo_ambito,
        "panel_delegaciones": list(delegaciones),
        "panel_funcionarios": list(funcionarios) if puede_filtrar_personal else [],
        "panel_periodos": list(Periodo.objects.order_by("-fecha_inicio")[:30]),
        "panel_puede_delegacion": administrador,
        "panel_puede_funcionario": puede_filtrar_personal,
        "panel_delegacion_id": seleccion_delegacion,
        "panel_funcionario_id": seleccion_funcionario,
        "panel_periodo_id": periodo.pk if periodo else None,
        "panel_total": total_actividades,
        "panel_aprobadas": conteo_estados.get(Actividad.Estado.APROBADA, 0),
        "panel_compromisos": total_agenda,
        "panel_estados": estados,
        "panel_agenda_estados": estados_agenda,
        "panel_tendencia": tendencia,
        "panel_comparativa": comparativa,
        "panel_comparativa_titulo": etiqueta_comparativa,
        "panel_metas": semaforos,
        "panel_metas_total": metas_totales,
    }
