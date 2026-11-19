"""Lee solo CABECERAS/OBJETIVOS de la matriz municipal; nunca carga datos personales de gestiones.
No ejecuta fórmulas del Excel ni presupone que los valores de caché son oficiales.
"""
from collections import Counter
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from io import BytesIO
from pathlib import PurePosixPath
import re
from xml.etree import ElementTree as ET
from zipfile import ZipFile, BadZipFile

MAX_BYTES = 8 * 1024 * 1024
MAX_DESCOMPRIMIDO = 80 * 1024 * 1024
NS = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
REL_NS = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}'

# Rango exacto donde el libro presenta sus ítems ponderados (no las gestiones).
# [nombre de hoja, columna del ítem, columna peso, columna objetivo, primera, última fila]
ESQUEMAS = (
    ('AP ADM.', 'B', 'E', 'F', 3, 7),
    ('COOR DISERCO', 'C', 'D', 'E', 3, 11),
    ('T OC1', 'B', 'D', 'E', 3, 8),
    ('T OC 2', 'B', 'D', 'E', 3, 8),
    ('T OC 3', 'B', 'D', 'E', 3, 8),
    ('T OC 4', 'B', 'D', 'E', 3, 8),
    ('G SOC 1', 'C', 'E', 'F', 3, 8),
    ('G SOC2', 'C', 'E', 'F', 3, 8),
    ('G SOC3', 'C', 'D', 'E', 3, 8),
    ('G SOC4', 'C', 'D', 'E', 3, 8),
    (' G SOC5', 'C', 'D', 'E', 3, 8),
    ('PLAN y CON', 'B', 'D', 'E', 3, 6),
    ('GES SEG', 'A', 'D', 'F', 3, 9),
)

class ErrorMatriz(ValueError):
    pass


def _normalizar(v):
    return re.sub(r'\s+', ' ', str(v or '')).strip()


def _texto_inline(elemento):
    return ''.join(t.text or '' for t in elemento.iter(NS+'t'))


def _decimal(v):
    try:
        if v is None or not str(v).strip():
            return None
        d = Decimal(str(v))
        return d if d.is_finite() else None
    except (InvalidOperation, ValueError):
        return None


def _hojas(archivo):
    try:
        workbook = ET.fromstring(archivo.read('xl/workbook.xml'))
        relaciones = ET.fromstring(archivo.read('xl/_rels/workbook.xml.rels'))
        paths = {n.get('Id'): n.get('Target') for n in relaciones}
        resultado = {}
        for s in workbook.find(NS+'sheets'):
            destino = paths.get(s.get(REL_NS+'id'), '')
            if destino.startswith('/xl/'):
                destino = destino[1:]
            elif destino.startswith('xl/'):
                pass
            else:
                destino = 'xl/' + destino.lstrip('/')
            if '..' in PurePosixPath(destino).parts or not re.fullmatch(r'xl/worksheets/sheet\d+\.xml', destino):
                continue
            resultado[s.get('name')] = destino
        return resultado
    except (KeyError, ET.ParseError, TypeError, AttributeError) as exc:
        raise ErrorMatriz('El archivo no contiene la estructura de hojas esperada.') from exc


def _compartidas(archivo):
    if 'xl/sharedStrings.xml' not in archivo.namelist():
        return []
    raiz = ET.fromstring(archivo.read('xl/sharedStrings.xml'))
    return [_texto_inline(si) for si in raiz.findall(NS+'si')]


def _valores_resumen(archivo, ruta, compartidas, max_fila=22):
    raiz = ET.fromstring(archivo.read(ruta))
    salida = {}
    for fila in raiz.findall('.//' + NS + 'sheetData/' + NS + 'row'):
        numero = int(fila.get('r', '0'))
        if numero > max_fila:
            break
        for celda in fila.findall(NS+'c'):
            direccion = celda.get('r', '')
            v = celda.find(NS+'v')
            f = celda.find(NS+'f')
            inline = celda.find(NS+'is')
            valor = v.text if v is not None else None
            if celda.get('t') == 's' and valor is not None:
                indice = int(valor)
                valor = compartidas[indice]
            elif inline is not None:
                valor = _texto_inline(inline)
            formula = f.text if f is not None and f.text else ''
            if valor is not None or formula:
                salida[direccion] = {'valor':valor, 'formula':formula}
    return salida


def _celda(celdas, posicion):
    return celdas.get(posicion, {'valor':None, 'formula':''})


def leer_matriz_xlsx(contenido):
    """Devuelve ítems serializables, avisos y resumen. No altera la BD."""
    if not contenido or len(contenido) > MAX_BYTES:
        raise ErrorMatriz('Selecciona un XLSX de máximo 8 MB.')
    try:
        with ZipFile(BytesIO(contenido)) as libro:
            entradas = libro.infolist()
            if len(entradas) > 300 or sum(e.file_size for e in entradas) > MAX_DESCOMPRIMIDO:
                raise ErrorMatriz('El archivo Excel excede el tamaño descomprimido permitido.')
            rutas = _hojas(libro)
            faltantes = [hoja for hoja, *_ in ESQUEMAS if hoja not in rutas]
            if faltantes:
                raise ErrorMatriz('El archivo no corresponde a la matriz esperada. Faltan hojas: ' + ', '.join(faltantes[:4]))
            compartidas = _compartidas(libro)
            registros, avisos = [], []
            for hoja, col_item, col_peso, col_meta, primera, ultima in ESQUEMAS:
                celdas = _valores_resumen(libro, rutas[hoja], compartidas)
                for n in range(primera, ultima+1):
                    posicion_item, posicion_peso, posicion_meta = f'{col_item}{n}', f'{col_peso}{n}', f'{col_meta}{n}'
                    item = _normalizar(_celda(celdas, posicion_item)['valor'])
                    if not item:
                        avisos.append(f'{hoja} fila {n}: ítem sin nombre; se omitió.')
                        continue
                    peso = _decimal(_celda(celdas, posicion_peso)['valor'])
                    origen = _celda(celdas, posicion_meta)
                    meta = _decimal(origen['valor'])
                    formula = origen['formula']
                    # Una meta que depende del mismo avance es una referencia CIRCULAR o
                    # variable: no cargar el valor de caché como objetivo oficial.
                    dinamica = bool(formula and re.fullmatch(r'[+]?[A-Z]{1,2}'+str(n), formula.strip()))
                    if dinamica:
                        clase, meta = 'DIN', None
                    elif meta is None or meta <= 0 or peso is None or peso <= 0 or peso > 1:
                        clase = 'REV'
                    elif meta < 1:
                        clase = 'PORC'
                    elif meta != meta.to_integral_value():
                        clase = 'REV'
                    else:
                        clase = 'CANT'
                    if clase != 'CANT':
                        avisos.append(f'{hoja} {posicion_item}: {item[:40]} requiere revisión ({clase}).')
                    ponderacion = (peso * 100).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP) if peso is not None else None
                    registros.append({
                        'hoja':hoja, 'fila':n, 'nombre':item[:200],
                        'ponderacion':str(ponderacion) if ponderacion is not None else None,
                        'meta_original':str(meta) if meta is not None else None,
                        'clase':clase, 'celda_item':posicion_item,
                        'celda_meta':posicion_meta, 'formula_meta':formula[:350],
                    })
                # Felicitaciones / reclamos: valores adicionales, NO se convierten
                # en cantidad de actividades ni se suman automáticamente.
                for n in range(primera, 22):
                    for col in ('A','B','C'):
                        label = _normalizar(_celda(celdas, f'{col}{n}')['valor'])
                        upper = label.upper()
                        if upper.startswith('FELICITACIONES') or upper == 'RECLAMOS':
                            candidatos = [_decimal(_celda(celdas, f'{c}{n}')['valor']) for c in ('D','E')]
                            peso = next((v for v in candidatos if v is not None and -1 <= v <= 1 and v != 0), None)
                            registros.append({
                                'hoja':hoja, 'fila':n, 'nombre':label[:200],
                                'ponderacion':str((peso * 100).quantize(Decimal('0.01'))) if peso is not None else None,
                                'meta_original':None, 'clase':'ESP',
                                'celda_item':f'{col}{n}', 'celda_meta':'', 'formula_meta':'',
                            })
                            break
            cantidades = dict(Counter(r['clase'] for r in registros))
            return registros, avisos, cantidades
    except (BadZipFile, KeyError, IndexError, ET.ParseError, ValueError, TypeError) as exc:
        if isinstance(exc, ErrorMatriz):
            raise
        raise ErrorMatriz('El Excel está dañado o no tiene el formato esperado.') from exc
