"""Regresiones de asignaciones y sumas por ámbito (datos sintéticos)."""
from datetime import date
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from catalogos.models import Cargo
from delegaciones.models import Delegacion
from funcionarios.models import Funcionario
from gestion.models import MetaIndicador, Periodo, ConfiguracionMetaSGR
from gestion.ponderaciones_sgr import comprobar_ponderacion, resumen_por_ambitos
from matriz_sgr.models import CatalogoMatrizSGR, ItemMatrizSGR, VinculoMatrizSGR, CorrespondenciaHojaCargoSGR
from gestion.medicion_eva3_forms import ConfiguracionMetaSGRForm

class ControlMatrizTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        U=get_user_model()
        cls.admin=U.objects.create_user(username='admin_auditoria',password='ClavePruebas_123!',rol='ADMIN')
        cls.delegacion=Delegacion.objects.create(nombre='Prueba de validación')
        cls.periodo=Periodo.objects.create(nombre='Periodo de auditoría',fecha_inicio=date(2026,10,1),fecha_fin=date(2026,12,31))
        cls.admin_cargo=Cargo.objects.create(nombre_cargo='Apoyo Administrativo')
        cls.territorial=Cargo.objects.create(nombre_cargo='Gestor Territorial')
        cls.func_territorial=Funcionario.objects.create(nombre='Funcionario territorial',rut='12345678-5',email='territorial@test.example',delegacion=cls.delegacion,cargo=cls.territorial)
        cls.func_adm=Funcionario.objects.create(nombre='Funcionaria administrativa',rut='23456765-9',email='adm@test.example',delegacion=cls.delegacion,cargo=cls.admin_cargo)
        cls.catalogo=CatalogoMatrizSGR.objects.create(nombre_archivo='Matriz-pruebas.xlsx',sha256='a'*64,importado_por=cls.admin)
        cls.item=ItemMatrizSGR.objects.create(catalogo=cls.catalogo,hoja='AP ADM.',fila=4,nombre='LLAMADAS PREVENTIVAS',ponderacion=Decimal('30'),meta_original=90,clase='CANT',celda_item='B4')
        cls.meta=MetaIndicador.objects.create(nombre='Llamadas preventivas - test',delegacion=cls.delegacion,periodo=cls.periodo,meta_cantidad=90,ponderacion=Decimal('30'))
        VinculoMatrizSGR.objects.create(item=cls.item,meta=cls.meta,creado_por=cls.admin)

    def test_meta_de_excel_sin_equivalencia_se_rechaza_al_configurar(self):
        form=ConfiguracionMetaSGRForm(data={'funcionario':self.func_territorial.pk,'cargo':self.territorial.pk,'funcion':'','tope_porcentaje':'120'},meta=self.meta,usuario=self.admin)
        self.assertFalse(form.is_valid())
        self.assertIn('cargo municipal asociado', str(form.non_field_errors()).lower())

    def test_cargo_diferente_a_hoja_rechazado(self):
        CorrespondenciaHojaCargoSGR.objects.create(catalogo=self.catalogo,hoja='AP ADM.',cargo=self.admin_cargo)
        form=ConfiguracionMetaSGRForm(data={'funcionario':self.func_territorial.pk,'cargo':self.territorial.pk,'funcion':'','tope_porcentaje':'120'},meta=self.meta,usuario=self.admin)
        self.assertFalse(form.is_valid())
        self.assertTrue('cargo' in form.errors or 'funcionario' in form.errors)

    def test_cargo_y_funcionario_compatibles(self):
        CorrespondenciaHojaCargoSGR.objects.create(catalogo=self.catalogo,hoja='AP ADM.',cargo=self.admin_cargo)
        form=ConfiguracionMetaSGRForm(data={'funcionario':self.func_adm.pk,'cargo':self.admin_cargo.pk,'funcion':'','tope_porcentaje':'120'},meta=self.meta,usuario=self.admin)
        self.assertTrue(form.is_valid(),form.errors)
        form.save()
        self.assertEqual(self.meta.configuracion_sgr.funcionario_id,self.func_adm.pk)

    def test_suma_superior_100_mismo_funcionario_rechazada(self):
        extra=MetaIndicador.objects.create(nombre='Extra',delegacion=self.delegacion,periodo=self.periodo,meta_cantidad=10,ponderacion=Decimal('80'))
        ConfiguracionMetaSGR.objects.create(meta=extra,funcionario=self.func_adm)
        CorrespondenciaHojaCargoSGR.objects.create(catalogo=self.catalogo,hoja='AP ADM.',cargo=self.admin_cargo)
        form=ConfiguracionMetaSGRForm(data={'funcionario':self.func_adm.pk,'cargo':self.admin_cargo.pk,'funcion':'','tope_porcentaje':'120'},meta=self.meta,usuario=self.admin)
        self.assertFalse(form.is_valid())
        self.assertIn('ponderacion',str(form.errors).lower())

    def test_distintos_funcionarios_no_se_mezclan(self):
        self.assertIsNone(comprobar_ponderacion(delegacion_id=self.delegacion.pk,periodo_id=self.periodo.pk,ponderacion=Decimal('100'),funcionario_id=self.func_territorial.pk))
        self.assertIsNone(comprobar_ponderacion(delegacion_id=self.delegacion.pk,periodo_id=self.periodo.pk,ponderacion=Decimal('100'),funcionario_id=self.func_adm.pk))

    def test_mapeo_no_cambia_datos_existentes(self):
        c=ConfiguracionMetaSGR.objects.create(meta=self.meta,funcionario=self.func_territorial,cargo=self.territorial)
        CorrespondenciaHojaCargoSGR.objects.create(catalogo=self.catalogo,hoja='AP ADM.',cargo=self.admin_cargo)
        c.refresh_from_db()
        self.assertEqual(c.funcionario,self.func_territorial)
        self.assertEqual(self.meta.ponderacion,Decimal('30'))

    def test_pagina_mapeo_solo_admin(self):
        url=reverse('matriz_sgr:equivalencias',args=[self.catalogo.pk])
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(url).status_code,200)
        U=get_user_model()
        otro=U.objects.create_user(username='no_admin_auditoria',password='ClavePruebas_123!',rol='FUNC')
        self.client.force_login(otro)
        self.assertEqual(self.client.get(url).status_code,403)

    def test_bonus_no_entran_en_base(self):
        grupos=resumen_por_ambitos(MetaIndicador.objects.filter(delegacion=self.delegacion))
        self.assertEqual(len(grupos),1)
        self.assertEqual(grupos[0]['total'],Decimal('30'))
