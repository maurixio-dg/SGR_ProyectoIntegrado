"""Pruebas de regresión Fase 4.1; no cambian datos reales."""
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from .clasificacion import sugerir_tipo
from .models import OrganizacionComunitaria


class FiltrosFase41Tests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.admin = User.objects.create_user(
            username='admin_org_f41', password='PruebaSegura123!', rol='ADMIN'
        )
        cls.junta = OrganizacionComunitaria.objects.create(
            nombre='JUNTA DE VECINOS NUEVA LA SERENA',
            tipo='SIN', estado_verificacion='PEND',
            fuente_archivo='catastro.xlsx', territorio_origen='ANTENA'
        )
        cls.club = OrganizacionComunitaria.objects.create(
            nombre='CLUB DEPORTIVO ESTRELLA',
            tipo='SIN', estado_verificacion='PEND',
            fuente_archivo='catastro.xlsx', territorio_origen='PAMPA'
        )
        cls.otro = OrganizacionComunitaria.objects.create(
            nombre='AGRUPACION VECINAL SIN TIPO',
            tipo='SIN', estado_verificacion='PEND',
            fuente_archivo='catastro.xlsx', territorio_origen='PAMPA'
        )
        cls.manual = OrganizacionComunitaria.objects.create(
            nombre='JUNTA DE VECINOS MANUAL',
            tipo='SIN', estado_verificacion='PEND',
            fuente_archivo='', territorio_origen='PAMPA'
        )

    def setUp(self):
        self.client.force_login(self.admin)

    def test_filtro_todos_muestra_organizaciones(self):
        resp = self.client.get(reverse('organizaciones:listar'))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context['pagina'].paginator.count, 4)
        self.assertEqual(resp.context['total_disponibles'], 4)

    def test_busqueda_y_territorio(self):
        resp = self.client.get(reverse('organizaciones:listar'),
                               {'buscar': 'ESTRELLA', 'territorio': 'PAMPA'})
        self.assertEqual(resp.context['pagina'].paginator.count, 1)
        self.assertContains(resp, 'CLUB DEPORTIVO ESTRELLA')

    def test_clasificador_conservador(self):
        self.assertEqual(sugerir_tipo('JUNTA DE VECINOS Nº 10'), 'JJVV')
        self.assertEqual(sugerir_tipo('CLUB DEPORTIVO LOS ANDES'), 'DEP')
        self.assertEqual(sugerir_tipo('COMITÉ DE VIVIENDA'), 'COM')
        self.assertIsNone(sugerir_tipo('AGRUPACION DE MUJERES JUNTAS POR LA VIDA'))
        self.assertIsNone(sugerir_tipo('UNION COMUNAL DE JUNTAS DE VECINOS'))

    def test_previsualizar_y_aplicar_sin_alterar_otras_columnas(self):
        salida = StringIO()
        call_command('clasificar_organizaciones', stdout=salida)
        self.junta.refresh_from_db()
        self.assertEqual(self.junta.tipo, 'SIN')
        self.assertContains(self.client.get(reverse('organizaciones:listar'), {'tipo': 'JJVV'}),
                            'No hay organizaciones para los filtros seleccionados')
        call_command('clasificar_organizaciones', aplicar=True, stdout=StringIO())
        self.junta.refresh_from_db()
        self.club.refresh_from_db()
        self.manual.refresh_from_db()
        self.otro.refresh_from_db()
        self.assertEqual(self.junta.tipo, 'JJVV')
        self.assertEqual(self.club.tipo, 'DEP')
        self.assertEqual(self.manual.tipo, 'SIN')
        self.assertEqual(self.otro.tipo, 'SIN')
        self.assertEqual(self.junta.estado_verificacion, 'PEND')
        resp = self.client.get(reverse('organizaciones:listar'), {'tipo': 'JJVV'})
        self.assertEqual(resp.context['pagina'].paginator.count, 1)
        self.assertContains(resp, 'JUNTA DE VECINOS NUEVA LA SERENA')
