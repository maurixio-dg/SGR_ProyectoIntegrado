"""Lee la estructura fija del Excel JJVV mediante bibliotecas estándar.

No ejecuta fórmulas, macros ni enlaces externos. No convierte nombres en
clasificaciones municipales sin revisión humana.
"""
from datetime import date, datetime, timedelta
import io
import posixpath
import re
import unicodedata
import zipfile
from xml.etree import ElementTree as ET

M = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
R = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}'
P = '{http://schemas.openxmlformats.org/package/2006/relationships}'
MAX_BYTES = 10 * 1024 * 1024
MAX_UNCOMPRESSED = 50 * 1024 * 1024
MAX_ROWS = 5000
HEADERS = ('ORGANIZACIONES', 'DOMICILIO LEGAL', 'TERRIT DELEG', 'SOCIOS ACTIVOS',
           'FECHA CONSTIT', 'N REG P J', 'FECHA INSCRIPC EN REG', 'REG DIR N')


class ErrorExcel(ValueError):
    pass


def _normalizar(texto):
    texto = unicodedata.normalize('NFKD', str(texto or '').upper())
    texto = ''.join(c for c in texto if not unicodedata.combining(c))
    return ' '.join(re.sub(r'[^A-Z0-9]+', ' ', texto).split())


def _texto(celda, compartidas):
    if celda.find(M + 'f') is not None:
        raise ErrorExcel('Se detectó una fórmula. El catastro debe contener valores, no fórmulas.')
    tipo = celda.attrib.get('t')
    valor = celda.find(M + 'v')
    if tipo == 'inlineStr':
        inline = celda.find(M + 'is')
        return ''.join(n.text or '' for n in inline.iter(M + 't')) if inline is not None else ''
    if valor is None or valor.text is None:
        return ''
    if tipo == 's':
        try:
            return compartidas[int(valor.text)]
        except (ValueError, IndexError):
            raise ErrorExcel('Índice de texto compartido no válido.') from None
    if tipo == 'e':
        raise ErrorExcel('Una celda contiene un error de Excel.')
    return valor.text


def _numero(value, etiqueta, fila, avisos):
    v = str(value or '').strip()
    if not v:
        return None
    try:
        n = int(float(v.replace(',', '.')))
        if n < 0 or n > 10_000_000 or float(v.replace(',', '.')) != n:
            raise ValueError()
        return n
    except (ValueError, OverflowError):
        avisos.append(f'Fila {fila}: {etiqueta} inválido; queda sin dato.')
        return None


def _identificador(value):
    v = str(value or '').strip()
    if re.fullmatch(r'\d+\.0+', v):
        v = v.partition('.')[0]
    return v[:50]


def _fecha(value, etiqueta, fila, avisos, date_1904=False):
    v = str(value or '').strip()
    if not v:
        return None
    try:
        n = float(v)
        if not 1 <= n <= 2958465:
            raise ValueError()
        origen = date(1904, 1, 1) if date_1904 else date(1899, 12, 30)
        resultado = origen + timedelta(days=int(n))
        if resultado.year < 1900 or resultado > date.today() + timedelta(days=3650):
            raise ValueError()
        return resultado
    except (ValueError, OverflowError):
        pass
    for formato in ('%d/%m/%Y', '%Y-%m-%d', '%d-%m-%Y'):
        try:
            return datetime.strptime(v, formato).date()
        except ValueError:
            continue
    avisos.append(f'Fila {fila}: {etiqueta} sin fecha reconocible; queda sin dato.')
    return None


def leer_catastro_xlsx(archivo):
    """Retorna (registros list[dict], avisos list[str]) sin crear objetos BD."""
    if hasattr(archivo, 'seek'):
        archivo.seek(0)
    contenido = archivo.read(MAX_BYTES + 1)
    if len(contenido) > MAX_BYTES:
        raise ErrorExcel('Archivo demasiado grande (máximo 10 MB).')
    try:
        paquete = zipfile.ZipFile(io.BytesIO(contenido))
    except zipfile.BadZipFile as exc:
        raise ErrorExcel('El archivo no es un Excel .xlsx válido.') from exc
    with paquete:
        integrantes = paquete.infolist()
        if (len(integrantes) > 1000 or sum(i.file_size for i in integrantes) > MAX_UNCOMPRESSED
                or any(i.file_size > MAX_UNCOMPRESSED for i in integrantes)):
            raise ErrorExcel('El Excel supera los límites de seguridad.')
        nombres = set(paquete.namelist())
        if 'xl/workbook.xml' not in nombres or 'xl/_rels/workbook.xml.rels' not in nombres:
            raise ErrorExcel('No se encontró la estructura del libro de Excel.')
        try:
            libro = ET.fromstring(paquete.read('xl/workbook.xml'))
            rels = ET.fromstring(paquete.read('xl/_rels/workbook.xml.rels'))
        except ET.ParseError as exc:
            raise ErrorExcel('El libro contiene XML inválido.') from exc
        mapa = {rel.get('Id'): rel.get('Target') for rel in rels.findall(P + 'Relationship')}
        hojas = libro.find(M + 'sheets')
        if hojas is None:
            raise ErrorExcel('El Excel no contiene hojas.')
        hoja = next((h for h in hojas if _normalizar(h.attrib.get('name')) == 'JUNTAS DE VECINOS'),
                    next(iter(hojas), None))
        if hoja is None:
            raise ErrorExcel('El Excel no contiene hojas.')
        destino = mapa.get(hoja.get(R + 'id'), '')
        ruta = (destino.lstrip('/') if destino.startswith('/') else posixpath.normpath(posixpath.join('xl', destino)))
        if not ruta.startswith('xl/worksheets/') or ruta not in nombres:
            raise ErrorExcel('No se encontró la hoja de organizaciones.')
        compartidas = []
        if 'xl/sharedStrings.xml' in nombres:
            try:
                strings = ET.fromstring(paquete.read('xl/sharedStrings.xml'))
            except ET.ParseError as exc:
                raise ErrorExcel('Tabla de textos del Excel inválida.') from exc
            compartidas = [''.join(t.text or '' for t in si.iter(M + 't'))
                           for si in strings.findall(M + 'si')]
        opciones = libro.find(M + 'workbookPr')
        fecha_1904 = opciones is not None and opciones.get('date1904') in ('1', 'true')
        try:
            hoja_xml = ET.fromstring(paquete.read(ruta))
        except ET.ParseError as exc:
            raise ErrorExcel('La hoja de organizaciones contiene XML inválido.') from exc
        tabla = hoja_xml.find(M + 'sheetData')
        if tabla is None:
            raise ErrorExcel('La hoja de organizaciones está vacía.')
        registros = []
        avisos = []
        primera = True
        for celda_fila in tabla.findall(M + 'row'):
            numero_fila = int(celda_fila.get('r', '0'))
            if numero_fila > MAX_ROWS + 1:
                raise ErrorExcel('El archivo supera las 5.000 filas permitidas.')
            fila = [''] * 8
            for celda in celda_fila.findall(M + 'c'):
                ref = celda.get('r', '')
                m = re.fullmatch(r'([A-Z]+)(\d+)', ref)
                if not m:
                    continue
                indice = 0
                for letra in m.group(1):
                    indice = indice * 26 + ord(letra) - 64
                if 1 <= indice <= 8:
                    fila[indice - 1] = _texto(celda, compartidas)
            if primera:
                primera = False
                esperados = [_normalizar(c) for c in HEADERS]
                obtenidos = [_normalizar(c) for c in fila]
                if obtenidos != esperados:
                    raise ErrorExcel('Las ocho columnas no coinciden con el catastro JJVV esperado. No se importó nada.')
                continue
            if not any(str(c).strip() for c in fila):
                continue
            nombre = str(fila[0]).strip()
            if not nombre:
                avisos.append(f'Fila {numero_fila}: sin nombre; no se importará.')
                continue
            if len(nombre) > 255:
                avisos.append(f'Fila {numero_fila}: nombre demasiado largo; no se importará.')
                continue
            reg = {
                'nombre': nombre,
                'domicilio_legal': str(fila[1] or '').strip()[:400],
                'territorio_origen': str(fila[2] or '').strip()[:80],
                'socios_activos': _numero(fila[3], 'socios activos', numero_fila, avisos),
                'fecha_constitucion': _fecha(fila[4], 'constitución', numero_fila, avisos, fecha_1904),
                'numero_registro_pj': _identificador(fila[5]) or None,
                'fecha_inscripcion': _fecha(fila[6], 'inscripción', numero_fila, avisos, fecha_1904),
                'registro_directorio': _identificador(fila[7]),
                'fila_origen': numero_fila,
            }
            registros.append(reg)
        if primera:
            raise ErrorExcel('La hoja no contiene una cabecera.')
        if not registros:
            raise ErrorExcel('No se encontraron organizaciones válidas.')
        return registros, avisos
