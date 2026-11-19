"""Pruebas seguras: no necesitan cargar datos personales del libro municipal."""
from io import BytesIO
from zipfile import ZipFile
from django.test import SimpleTestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from .lector_matriz import ESQUEMAS, leer_matriz_xlsx, ErrorMatriz


def libro_de_prueba():
    # Hojas mínimas con celdas en la posición prevista; sin biblioteca de Excel ni macros.
    buf = BytesIO()
    with ZipFile(buf, 'w') as z:
        nombres = ''.join(f'<sheet name="{nombre.replace("&", "&amp;")}" sheetId="{i}" r:id="rId{i}"/>' for i,(nombre,*_) in enumerate(ESQUEMAS,1))
        z.writestr('xl/workbook.xml', f'<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>{nombres}</sheets></workbook>')
        links = ''.join(f'<Relationship Id="rId{i}" Target="worksheets/sheet{i}.xml" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet"/>' for i in range(1,len(ESQUEMAS)+1))
        z.writestr('xl/_rels/workbook.xml.rels',f'<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">{links}</Relationships>')
        for i, (nombre, it, peso, meta, primero, ultimo) in enumerate(ESQUEMAS,1):
            z.writestr(f'xl/worksheets/sheet{i}.xml',f'''<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData><row r="{primero}"><c r="{it}{primero}" t="inlineStr"><is><t>ATENCION DE USUARIO</t></is></c><c r="{peso}{primero}"><v>0.2</v></c><c r="{meta}{primero}"><v>240</v></c></row></sheetData></worksheet>''')
    return buf.getvalue()


class LectorMatrizTests(SimpleTestCase):
    def test_lee_13_hojas_y_solo_metas(self):
        filas, avisos, resumen = leer_matriz_xlsx(libro_de_prueba())
        self.assertEqual(len(filas), len(ESQUEMAS))
        self.assertEqual(resumen['CANT'], len(ESQUEMAS))
        self.assertEqual(filas[0]['ponderacion'], '20.00')
        self.assertEqual(filas[0]['meta_original'], '240')
        self.assertEqual(filas[0]['celda_item'], 'B3')

    def test_no_acepta_otro_formato(self):
        with self.assertRaises(ErrorMatriz):
            leer_matriz_xlsx(b'NO ES XLSX')
