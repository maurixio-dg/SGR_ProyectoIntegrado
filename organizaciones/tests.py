"""Pruebas del CRUD, permisos y carga controlada del Excel JJVV."""
from io import BytesIO
from zipfile import ZipFile, ZIP_DEFLATED
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from .models import OrganizacionComunitaria
from .xlsx_import import leer_catastro_xlsx


ENCABEZADOS = ['ORGANIZACIONES', 'DOMICILIO LEGAL ', 'TERRIT. DELEG.',
               'SOCIOS ACTIVOS', 'FECHA CONSTIT.', 'Nº REG. P.J.',
               'FECHA INSCRIPC EN REG.', 'REG. DIR. Nº']


def excel_ejemplo():
    from xml.sax.saxutils import escape
    from string import ascii_uppercase
    filas = [ENCABEZADOS,
             ['CLUB DE PRUEBA', 'Calle de prueba 123', 'PAMPA', '15',
              '46172', '4006', '46181', '9001'],
             ['CLUB REPETIDO', 'Calle de prueba 456', 'CENTRO', '30',
              '46172', '4006', '46181', '9002']]
    xml_rows = []
    for i, vals in enumerate(filas, 1):
        cells = ''.join(
            f'<c r="{ascii_uppercase[j]}{i}" t="inlineStr"><is><t>{escape(v)}</t></is></c>'
            for j, v in enumerate(vals)
        )
        xml_rows.append(f'<row r="{i}">{cells}</row>')
    sheet = ('<?xml version="1.0" encoding="UTF-8"?>'
             '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
             '<sheetData>' + ''.join(xml_rows) + '</sheetData></worksheet>')
    wb = ('<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
          'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
          '<sheets><sheet name="juntas de vecinos" sheetId="1" r:id="rId1"/></sheets></workbook>')
    rels = ('<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
            'Target="worksheets/sheet1.xml"/></Relationships>')
    destino = BytesIO()
    with ZipFile(destino, 'w', ZIP_DEFLATED) as z:
        z.writestr('xl/workbook.xml', wb)
        z.writestr('xl/_rels/workbook.xml.rels', rels)
        z.writestr('xl/worksheets/sheet1.xml', sheet)
    return destino.getvalue()


class OrganizacionesEVA4Tests(TestCase):
    @classmethod
    def setUpTestData(cls):
        U = get_user_model()
        cls.admin = U.objects.create_user(username='admin_org_eva4', password='PruebaSegura123!', rol='ADMIN')
        cls.func = U.objects.create_user(username='func_org_eva4', password='PruebaSegura123!', rol='FUNC')

    def test_parser_y_excel_en_formato_original(self):
        filas, avisos = leer_catastro_xlsx(BytesIO(excel_ejemplo()))
        self.assertEqual(len(filas), 2)
        self.assertEqual(filas[0]['nombre'], 'CLUB DE PRUEBA')
        self.assertEqual(filas[0]['numero_registro_pj'], '4006')
        self.assertEqual(filas[0]['fecha_constitucion'].year, 2026)

    def test_previsualizar_sin_insertar_y_confirmar_sin_duplicar(self):
        self.client.force_login(self.admin)
        url = reverse('organizaciones:importar')
        def subir():
            return self.client.post(url, {'accion': 'previsualizar',
                'archivo': SimpleUploadedFile('catastro.xlsx', excel_ejemplo(),
                                              content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')})
        previo = subir()
        self.assertEqual(previo.status_code, 200)
        self.assertEqual(OrganizacionComunitaria.objects.count(), 0)
        self.assertEqual(previo.context['total'], 2)
        self.assertEqual(previo.context['nuevos'], 1)
        self.assertEqual(previo.context['duplicados'], 1)
        ok = self.client.post(url, {'accion': 'confirmar', 'token': previo.context['token']})
        self.assertEqual(ok.status_code, 302)
        self.assertEqual(OrganizacionComunitaria.objects.count(), 1)
        org = OrganizacionComunitaria.objects.get()
        self.assertEqual(org.estado_verificacion, 'PEND')
        self.assertIsNone(org.delegacion)
        self.assertEqual(org.territorio_origen, 'PAMPA')
        nuevo = subir()
        self.assertEqual(nuevo.context['nuevos'], 0)

    def test_importacion_restringida_y_anonima(self):
        url = reverse('organizaciones:importar')
        self.assertEqual(self.client.get(url).status_code, 302)
        self.client.force_login(self.func)
        self.assertEqual(self.client.get(url).status_code, 403)
        self.assertEqual(self.client.post(url, {'accion': 'confirmar', 'token': 'invalido'}).status_code, 403)

    def test_crud_restringido_y_lectura_de_pendientes(self):
        org = OrganizacionComunitaria.objects.create(nombre='ORGANIZACIÓN PENDIENTE',
                        estado_verificacion=OrganizacionComunitaria.Verificacion.PENDIENTE)
        self.client.force_login(self.func)
        self.assertEqual(self.client.get(reverse('organizaciones:crear')).status_code, 403)
        self.assertEqual(self.client.get(reverse('organizaciones:editar', args=[org.pk])).status_code, 403)
        self.assertNotContains(self.client.get(reverse('organizaciones:listar')), 'ORGANIZACIÓN PENDIENTE')
        self.client.force_login(self.admin)
        self.assertContains(self.client.get(reverse('organizaciones:listar')), 'ORGANIZACIÓN PENDIENTE')
        self.assertEqual(self.client.get(reverse('organizaciones:eliminar', args=[org.pk])).status_code, 200)
        self.assertTrue(OrganizacionComunitaria.objects.filter(pk=org.pk).exists())
        self.assertEqual(self.client.post(reverse('organizaciones:eliminar', args=[org.pk])).status_code, 302)
        self.assertFalse(OrganizacionComunitaria.objects.filter(pk=org.pk).exists())
