"""Auditoría de ponderaciones POR ÁMBITO; los extras especiales no son metas base.

No altera los avances ni calcula nuevamente los indicadores: se limita a
impedir nuevas combinaciones incoherentes y a reportar las preexistentes.
"""
from collections import defaultdict
from decimal import Decimal

CIEN = Decimal("100.00")

def clave_ambito(funcionario_id=None, cargo_id=None):
    if funcionario_id:
        return ("funcionario", int(funcionario_id))
    if cargo_id:
        return ("cargo", int(cargo_id))
    return ("delegacion", None)

def config_de_meta(meta):
    from .models import ConfiguracionMetaSGR
    try:
        return meta.configuracion_sgr
    except ConfiguracionMetaSGR.DoesNotExist:
        return None

def clave_de_meta(meta):
    c = config_de_meta(meta)
    return clave_ambito(c.funcionario_id if c else None, c.cargo_id if c else None)

def etiqueta_ambito(clave, nombres_funcionarios=None, nombres_cargos=None):
    tipo, pk = clave
    if tipo == 'funcionario':
        return 'Funcionario: ' + str((nombres_funcionarios or {}).get(pk, pk))
    if tipo == 'cargo':
        return 'Cargo: ' + str((nombres_cargos or {}).get(pk, pk))
    return 'Delegación (meta general)'

def total_proyectado(*, delegacion_id, periodo_id, funcionario_id=None, cargo_id=None,
                     excluir_meta_id=None):
    """Devuelve la suma en el ámbito propuesto, sin metas especiales ni inactivas."""
    from .models import MetaIndicador
    clave = clave_ambito(funcionario_id, cargo_id)
    metas = MetaIndicador.objects.filter(
        delegacion_id=delegacion_id, periodo_id=periodo_id, activo=True,
    ).select_related('configuracion_sgr')
    if excluir_meta_id:
        metas = metas.exclude(pk=excluir_meta_id)
    total = Decimal('0.00')
    for meta in metas:
        if clave_de_meta(meta) == clave:
            total += meta.ponderacion
    return total

def comprobar_ponderacion(*, delegacion_id, periodo_id, ponderacion,
                         funcionario_id=None, cargo_id=None, excluir_meta_id=None):
    if not delegacion_id or not periodo_id or ponderacion is None:
        return None
    anterior = total_proyectado(
        delegacion_id=delegacion_id, periodo_id=periodo_id,
        funcionario_id=funcionario_id, cargo_id=cargo_id,
        excluir_meta_id=excluir_meta_id,
    )
    nuevo = anterior + Decimal(ponderacion)
    if nuevo > CIEN:
        return (f'Las ponderaciones de este ámbito y período sumarían {nuevo:.2f}% '
                f'(ya asignado: {anterior:.2f}%). El total base no puede superar el 100%. '
                'Revise las metas activas o sus asignaciones; felicitaciones/reclamos van aparte.')
    return None

def estado_cargo_matriz(meta, funcionario=None, cargo=None, funcion=None):
    """Devuelve (errores de campo, texto informativo), sin cambiar datos."""
    from matriz_sgr.models import VinculoMatrizSGR, CorrespondenciaHojaCargoSGR
    vinculo = VinculoMatrizSGR.objects.select_related('item').filter(meta=meta).first() if meta.pk else None
    if not vinculo:
        return {}, ''
    item = vinculo.item
    mapa = CorrespondenciaHojaCargoSGR.objects.select_related('cargo').filter(
        catalogo_id=item.catalogo_id, hoja=item.hoja,
    ).first()
    if not mapa:
        return {'__all__': (f'La hoja «{item.hoja}» de la matriz no tiene un cargo '
                'municipal asociado. Abra «Matriz SGR → Cargos por hoja» y defínalo primero.')}, ''
    errores = {}
    if funcionario is not None and funcionario.cargo_id != mapa.cargo_id:
        errores['funcionario'] = (f'Esta meta viene de «{item.hoja}», asociada al cargo '
                                f'«{mapa.cargo.nombre_cargo}». El funcionario elegido tiene '
                                f'«{funcionario.cargo.nombre_cargo}».')
    if cargo is not None and cargo.pk != mapa.cargo_id:
        errores['cargo'] = f'El cargo de esta hoja de matriz debe ser «{mapa.cargo.nombre_cargo}».'
    if funcion is not None and funcion.cargo_id != mapa.cargo_id:
        errores['funcion'] = 'La función elegida no pertenece al cargo de la hoja de matriz.'
    if funcionario is None and cargo is None:
        errores['cargo'] = (f'Seleccione el cargo «{mapa.cargo.nombre_cargo}» '
                            'para evitar que esta meta se contabilice como general de delegación.')
    return errores, f'Hoja {item.hoja} → {mapa.cargo.nombre_cargo}'

def resumen_por_ambitos(metas):
    """Agrupa solo metas BASE activas por (delegación, período, funcionario/cargo)."""
    from funcionarios.models import Funcionario
    from catalogos.models import Cargo
    grupos = defaultdict(lambda: {'total': Decimal('0'), 'metas': []})
    metas = list(metas)
    for m in metas:
        if not m.activo:
            continue
        clave = (m.delegacion_id, m.periodo_id, clave_de_meta(m))
        grupos[clave]['total'] += m.ponderacion
        grupos[clave]['metas'].append(m)
    funcionarios = {x.pk:x.nombre for x in Funcionario.objects.filter(
        pk__in=[k[2][1] for k in grupos if k[2][0]=='funcionario'])}
    cargos = {x.pk:x.nombre_cargo for x in Cargo.objects.filter(
        pk__in=[k[2][1] for k in grupos if k[2][0]=='cargo'])}
    salida=[]
    for (did,pid,ambito),g in sorted(grupos.items(), key=lambda x:(x[0][0],x[0][1],str(x[0][2]))):
        ref = g['metas'][0]
        total=g['total']
        salida.append({
            'delegacion':ref.delegacion, 'periodo':ref.periodo,
            'ambito':etiqueta_ambito(ambito,funcionarios,cargos), 'total':total,
            'metas':g['metas'],
            'estado':('EXCESO' if total > CIEN else 'COMPLETO' if total == CIEN else 'INCOMPLETO'),
        })
    return salida
