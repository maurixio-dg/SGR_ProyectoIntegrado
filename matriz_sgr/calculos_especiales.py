"""Resultados independientes y auditables, SIN agregarlos al consolidado general.

La ponderación sólo puede agregarse al total oficial una vez definidas y
verificadas todas las metas del mismo cargo, período y alcance.
"""
from decimal import Decimal, ROUND_HALF_UP

DOS = Decimal('0.01')
TOPE = Decimal('120')
CIEN = Decimal('100')


def calcular_especial(medicion):
    """Devuelve porcentajes como Decimal o None si no hay datos validados."""
    item = medicion.item
    resultado = {
        'medicion': medicion, 'observado': None, 'objetivo': None,
        'cumplimiento': None, 'aporte': None, 'tope': TOPE,
    }
    if medicion.estado != 'VAL':
        return resultado
    if item.clase == 'PORC':
        if (not item.meta_original or not medicion.recibidos
                or medicion.resueltos is None or medicion.resueltos > medicion.recibidos):
            return resultado
        observado = Decimal(medicion.resueltos) * CIEN / Decimal(medicion.recibidos)
        objetivo = item.meta_original * CIEN
    elif item.clase == 'DIN':
        if not medicion.objetivo_variable or medicion.realizado_variable is None:
            return resultado
        observado = Decimal(medicion.realizado_variable)
        objetivo = Decimal(medicion.objetivo_variable)
    else:
        return resultado
    if objetivo <= 0 or item.ponderacion is None or item.ponderacion < 0:
        return resultado
    bruto = observado * CIEN / objetivo
    cumplimiento = min(TOPE, bruto)
    resultado.update(
        observado=observado.quantize(DOS, rounding=ROUND_HALF_UP),
        objetivo=objetivo.quantize(DOS, rounding=ROUND_HALF_UP),
        cumplimiento=cumplimiento.quantize(DOS, rounding=ROUND_HALF_UP),
        aporte=(cumplimiento * item.ponderacion / CIEN).quantize(DOS, rounding=ROUND_HALF_UP),
    )
    return resultado
