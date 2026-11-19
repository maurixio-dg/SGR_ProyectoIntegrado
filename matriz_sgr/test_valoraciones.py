"""Pruebas de felicitaciones y reclamos formales, con perfiles y respaldos sintéticos."""
import tempfile
from datetime import date
from decimal import Decimal
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from catalogos.models import Cargo
from delegaciones.models import Delegacion
from funcionarios.models import Funcionario
from gestion.models import Periodo
from .models import CatalogoMatrizSGR, ItemMatrizSGR
from .modelos_valoraciones import ValoracionCiudadanaSGR, AuditoriaValoracionCiudadanaSGR


class ValoracionesFormalesTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        U = get_user_model()
        cls.admin = U.objects.create_superuser(username='admin_valoraciones', email='admin@test.example', password='Clave-1!')
        cls.delegado = U.objects.create_user(username='delegado_valoraciones', password='Clave-1!', rol='DELEG')
        cls.delegado_sur = U.objects.create_user(username='delegado_sur', password='Clave-1!', rol='DELEG')
        cls.func_usuario = U.objects.create_user(username='func_usuario', password='Clave-1!', rol='FUNC')
        cls.norte = Delegacion.objects.create(nombre='Delegación de prueba Norte')
        cls.sur = Delegacion.objects.create(nombre='Delegación de prueba Sur')
        cls.cargo = Cargo.objects.create(nombre_cargo='Delegado de prueba')
        Funcionario.objects.create(nombre='Delegado Norte', rut='11111111-1', email='dn@test.example',
                                   delegacion=cls.norte, cargo=cls.cargo, usuario=cls.delegado)
        Funcionario.objects.create(nombre='Delegado Sur', rut='22222222-2', email='ds@test.example',
                                   delegacion=cls.sur, cargo=cls.cargo, usuario=cls.delegado_sur)
        cls.periodo = Periodo.objects.create(nombre='Periodo de prueba',fecha_inicio=date(2026,10,1),fecha_fin=date(2026,12,31))
        cls.catalogo = CatalogoMatrizSGR.objects.create(nombre_archivo='demo.xlsx', sha256='3'*64, importado_por=cls.admin)
        cls.feli = ItemMatrizSGR.objects.create(catalogo=cls.catalogo,hoja='AP ADM.',fila=9,
            nombre='FELICITACIONES',ponderacion=Decimal('10'),clase='ESP',celda_item='B9')
        cls.recl = ItemMatrizSGR.objects.create(catalogo=cls.catalogo,hoja='AP ADM.',fila=10,
            nombre='RECLAMOS',ponderacion=Decimal('-30'),clase='ESP',celda_item='B10')

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.override = override_settings(MEDIA_ROOT=self.tmp.name)
        self.override.enable()
        self.addCleanup(self.override.disable)
        self.addCleanup(self.tmp.cleanup)

    def datos(self, item=None, referencia='DOC-PRUEBA-001', medio='DELEG', respaldo=True):
        data = {
            'item': (item or self.feli).pk, 'periodo': self.periodo.pk,
            'fecha_documento':'2026-11-14','referencia':referencia,
            'remitente':'Vecino ficticio', 'medio':medio,
            'descripcion':'Documento ficticio formal recibido para validar el SGR.'
        }
        files = {'respaldo':SimpleUploadedFile('oficio.pdf',b'%PDF-1.4\ncontenido sintetico',content_type='application/pdf')} if respaldo else {}
        return data,files

    def crear(self,**kwargs):
        self.client.force_login(self.delegado)
        data, files = self.datos(**kwargs)
        return self.client.post(reverse('matriz_sgr:valoracion_crear'),{**data, **files},follow=False)

    def test_delegado_registra_felicitacion_con_respaldo_y_auditoria(self):
        r=self.crear()
        self.assertEqual(r.status_code,302)
        v=ValoracionCiudadanaSGR.objects.get()
        self.assertEqual(v.estado,'PEN')
        self.assertEqual(v.delegacion,self.norte)
        self.assertEqual(v.informado_por,self.delegado)
        self.assertEqual(v.historial.count(),1)
        self.assertTrue(Path(v.respaldo.path).exists())

    def test_rechaza_felicitacion_por_mensaje_directo_al_gestor(self):
        r=self.crear(medio='FUNC')
        self.assertEqual(r.status_code,200)
        self.assertContains(r,'no es elegible')
        self.assertFalse(ValoracionCiudadanaSGR.objects.exists())

    def test_sin_respaldo_no_permite_ingreso(self):
        r=self.crear(respaldo=False)
        self.assertEqual(r.status_code,200)
        self.assertContains(r,'Adjunte un documento formal')
        self.assertFalse(ValoracionCiudadanaSGR.objects.exists())

    def test_funcionario_normal_no_puede_crear(self):
        self.client.force_login(self.func_usuario)
        self.assertEqual(self.client.get(reverse('matriz_sgr:valoracion_crear')).status_code,403)

    def test_administrador_revisa_sin_sumar_puntaje(self):
        self.crear()
        v=ValoracionCiudadanaSGR.objects.get()
        self.client.force_login(self.admin)
        r=self.client.post(reverse('matriz_sgr:valoracion_detalle',args=[v.pk]),{
            'decision':'VAL','observacion':'Documento formal revisado y validado solamente como respaldo.'
        })
        self.assertEqual(r.status_code,302)
        v.refresh_from_db()
        self.assertEqual(v.estado,'VAL')
        self.assertEqual(v.historial.count(),2)
        self.assertEqual(v.item.ponderacion,Decimal('10'))
        self.assertFalse(hasattr(v,'aporte'))

    def test_delegado_no_puede_validar(self):
        self.crear()
        v=ValoracionCiudadanaSGR.objects.get()
        r=self.client.post(reverse('matriz_sgr:valoracion_detalle',args=[v.pk]),{
            'decision':'VAL','observacion':'Intento de validación sin permiso suficiente.'
        })
        self.assertEqual(r.status_code,403)
        v.refresh_from_db()
        self.assertEqual(v.estado,'PEN')

    def test_delegado_otra_delegacion_no_puede_ver(self):
        self.crear()
        v=ValoracionCiudadanaSGR.objects.get()
        self.client.force_login(self.delegado_sur)
        self.assertEqual(self.client.get(reverse('matriz_sgr:valoracion_detalle',args=[v.pk])).status_code,404)
        self.assertEqual(self.client.get(reverse('matriz_sgr:valoracion_respaldo',args=[v.pk])).status_code,404)

    def test_administrador_puede_descargar_respaldo_privado(self):
        self.crear()
        v=ValoracionCiudadanaSGR.objects.get()
        self.client.force_login(self.admin)
        r=self.client.get(reverse('matriz_sgr:valoracion_respaldo',args=[v.pk]))
        self.assertEqual(r.status_code,200)
        self.assertIn('attachment',r['Content-Disposition'])
        r.close()

    def test_no_duplicar_referencia_en_la_misma_delegacion_y_periodo(self):
        self.assertEqual(self.crear().status_code,302)
        r=self.crear(item=self.recl)
        self.assertEqual(r.status_code,200)
        self.assertEqual(ValoracionCiudadanaSGR.objects.count(),1)

    def test_reclamo_con_porcentaje_negativo_puede_guardarse_sin_descontar(self):
        r=self.crear(item=self.recl)
        self.assertEqual(r.status_code,302)
        v=ValoracionCiudadanaSGR.objects.get()
        self.assertEqual(v.item.ponderacion,Decimal('-30'))
        self.assertEqual(v.estado,'PEN')

    def test_validada_no_se_puede_revisar_dos_veces(self):
        self.crear()
        v=ValoracionCiudadanaSGR.objects.get()
        self.client.force_login(self.admin)
        url=reverse('matriz_sgr:valoracion_detalle',args=[v.pk])
        data={'decision':'VAL','observacion':'Documento revisado y aprobado por el administrador.'}
        self.assertEqual(self.client.post(url,data).status_code,302)
        self.assertEqual(self.client.post(url,data).status_code,403)
        self.assertEqual(AuditoriaValoracionCiudadanaSGR.objects.filter(valoracion=v).count(),2)
