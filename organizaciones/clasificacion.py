"""Sugerencias conservadoras de tipo según el nombre del catastro.

Una clasificación sugerida NO equivale a verificar los datos municipales.
Solo se aplica a encabezados inequívocos; el resto permanece SIN.
"""
import re
import unicodedata


def normalizar_nombre(nombre):
    texto = unicodedata.normalize('NFKD', str(nombre or '').upper())
    texto = ''.join(c for c in texto if not unicodedata.combining(c))
    return ' '.join(re.sub(r'[^A-Z0-9]+', ' ', texto).split())


_PATRONES = (
    ('JJVV', re.compile(r'^JUNTA (?:DE )?VECIN(?:OS|AL)\b')),
    ('COM', re.compile(r'^COMITE\b')),
    ('AM', re.compile(
        r'^(?:CLUB|CENTRO|AGRUPACION|ORGANIZACION) '
        r'(?:(?:DE|DEL|PARA|LOS|LAS) )?(?:ADULTOS? MAYORES?|TERCERA EDAD)\b'
    )),
    ('DEP', re.compile(
        r'^(?:CLUB DEPORTIVO|ORGANIZACION DEPORTIVA|AGRUPACION DEPORTIVA|'
        r'ASOCIACION DEPORTIVA|ESCUELA DE FUTBOL|ACADEMIA DEPORTIVA)\b'
    )),
    ('CUL', re.compile(
        r'^(?:(?:AGRUPACION|ORGANIZACION|CENTRO|CORPORACION|CLUB) '
        r'(?:CULTURAL|ARTISTICA|FOLCLORICA)|ACADEMIA DE MUSICA)\b'
    )),
    ('JUV', re.compile(
        r'^(?:AGRUPACION|ORGANIZACION|CLUB|CENTRO) '
        r'(?:(?:DE|PARA) )?(?:JOVENES|JUVENIL)\b'
    )),
)


def sugerir_tipo(nombre):
    texto = normalizar_nombre(nombre)
    for tipo, patron in _PATRONES:
        if patron.search(texto):
            return tipo
    return None
