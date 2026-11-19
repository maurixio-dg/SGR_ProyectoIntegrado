"""Cálculos de resultados y semáforos para metas asociadas a actividades validadas."""
from datetime import timedelta
from decimal import Decimal, ROUND_HALF_UP

from django.utils import timezone
from .models import ActividadIndicador, AusenciaSGR, ConfiguracionMetaSGR

CIEN = Decimal("100")
SESENTA = Decimal("60")
DOS_DECIMALES = Decimal("0.01")


def contar_habiles(inicio, fin):
    """Lunes a viernes; feriados particulares se abordarán al parametrizar el calendario."""
    if not inicio or not fin or fin < inicio:
        return 0
    dias = (fin - inicio).days + 1
    semanas, resto = divmod(dias, 7)
    return semanas * 5 + sum(1 for i in range(resto) if (inicio.weekday() + i) % 7 < 5)


def dias_ausencia(empleado_id, periodo, hasta):
    if not empleado_id or hasta < periodo.fecha_inicio:
        return 0, 0
    inicio = periodo.fecha_inicio
    fin = periodo.fecha_fin
    hasta = min(fin, hasta)
    ausentes = set()
    for ausencia in AusenciaSGR.objects.filter(
        funcionario_id=empleado_id, fecha_inicio__lte=fin, fecha_fin__gte=inicio
    ).only("fecha_inicio", "fecha_fin"):
        comienzo = max(inicio, ausencia.fecha_inicio)
        termino = min(fin, ausencia.fecha_fin)
        dia = comienzo
        while dia <= termino:
            if dia.weekday() < 5:
                ausentes.add(dia)
            dia += timedelta(days=1)
    return len(ausentes), sum(1 for dia in ausentes if dia <= hasta)


def meta_aplica_a_actividad(meta, actividad):
    """Evita asignar metas de otro responsable o cargo."""
    if actividad.delegacion_id != meta.delegacion_id:
        return False
    if not meta.periodo.fecha_inicio <= actividad.fecha_actividad <= meta.periodo.fecha_fin:
        return False
    try:
        configuracion = meta.configuracion_sgr
    except ConfiguracionMetaSGR.DoesNotExist:
        return True
    if configuracion.funcionario_id and actividad.funcionario_id != configuracion.funcionario_id:
        return False
    cargo_id = configuracion.cargo_id
    if configuracion.funcion_id and not cargo_id:
        cargo_id = configuracion.funcion.cargo_id
    if cargo_id and actividad.funcionario.cargo_id != cargo_id:
        return False
    return True


def calcular_resumen_meta(meta, hoy=None):
    hoy = hoy or timezone.localdate()
    periodo = meta.periodo
    try:
        configuracion = meta.configuracion_sgr
    except ConfiguracionMetaSGR.DoesNotExist:
        configuracion = None
    funcionario_id = configuracion.funcionario_id if configuracion else None
    cargo_id = configuracion.cargo_id if configuracion else None
    if configuracion and configuracion.funcion_id and not cargo_id:
        cargo_id = configuracion.funcion.cargo_id
    tope = configuracion.tope_porcentaje if configuracion else Decimal("120.00")

    asignaciones = ActividadIndicador.objects.filter(meta=meta).select_related(
        "actividad", "actividad__funcionario", "actividad__delegacion"
    )
    cantidad = 0
    for asignacion in asignaciones:
        actividad = asignacion.actividad
        if not actividad.elegible_para_puntaje:
            continue
        if funcionario_id and actividad.funcionario_id != funcionario_id:
            continue
        if cargo_id and actividad.funcionario.cargo_id != cargo_id:
            continue
        if not periodo.fecha_inicio <= actividad.fecha_actividad <= periodo.fecha_fin:
            continue
        cantidad += 1

    habiles_totales = contar_habiles(periodo.fecha_inicio, periodo.fecha_fin)
    habiles_transcurridos = contar_habiles(periodo.fecha_inicio, min(hoy, periodo.fecha_fin))
    ausentes_totales, ausentes_hasta_hoy = dias_ausencia(funcionario_id, periodo, hoy)
    dias_ajustados = max(0, habiles_totales - ausentes_totales)
    dias_transcurridos = max(0, habiles_transcurridos - ausentes_hasta_hoy)

    # Meta proporcional a los días computables, sin cambiar el objetivo original en la BD.
    meta_ajustada = (Decimal(meta.meta_cantidad) * Decimal(dias_ajustados) / Decimal(habiles_totales)).quantize(DOS_DECIMALES, rounding=ROUND_HALF_UP) if habiles_totales else Decimal("0")
    porcentaje_bruto = (Decimal(cantidad) * CIEN / meta_ajustada) if meta_ajustada > 0 else Decimal("0")
    porcentaje = min(porcentaje_bruto, tope)
    esperado = (Decimal(dias_transcurridos) * CIEN / Decimal(dias_ajustados)) if dias_ajustados else Decimal("0")
    esperado = min(esperado, CIEN)
    if not habiles_totales or not dias_ajustados or hoy < periodo.fecha_inicio:
        semaforo = "PENDIENTE"
    elif porcentaje >= esperado:
        semaforo = "VERDE"
    elif porcentaje >= esperado * SESENTA / CIEN:
        semaforo = "AMBAR"
    else:
        semaforo = "ROJO"
    aporte = (porcentaje * meta.ponderacion / CIEN).quantize(DOS_DECIMALES, rounding=ROUND_HALF_UP)
    return {
        "meta": meta, "cantidad": cantidad,
        "porcentaje": porcentaje.quantize(DOS_DECIMALES, rounding=ROUND_HALF_UP),
        "porcentaje_bruto": porcentaje_bruto.quantize(DOS_DECIMALES, rounding=ROUND_HALF_UP),
        "aporte_ponderado": aporte,
        "meta_ajustada": meta_ajustada,
        "cumplida": meta_ajustada > 0 and Decimal(cantidad) >= meta_ajustada,
        "esperado": esperado.quantize(DOS_DECIMALES, rounding=ROUND_HALF_UP),
        "semaforo": semaforo, "tope": tope,
        "dias_computables": dias_ajustados,
        "dias_transcurridos": dias_transcurridos,
        "ausencias_dias": ausentes_totales,
        "configuracion": configuracion,
    }
