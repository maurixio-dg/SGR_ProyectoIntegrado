"""Pruebas de cálculos de porcentajes y objetivos variables, sin depender de datos reales."""
from decimal import Decimal
from types import SimpleNamespace

from django.test import SimpleTestCase
from django.core.exceptions import ValidationError
from .calculos_especiales import calcular_especial
from .modelos_especiales import MedicionEspecialSGR
from .models import ItemMatrizSGR


class CalculosEspecialesTests(SimpleTestCase):
    def test_ocho_de_diez_resueltas_cumple_objetivo_80(self):
        item = SimpleNamespace(clase='PORC', meta_original=Decimal('0.8'), ponderacion=Decimal('25'))
        m = SimpleNamespace(item=item, estado='VAL', resueltos=8, recibidos=10)
        r = calcular_especial(m)
        self.assertEqual(r['observado'], Decimal('80.00'))
        self.assertEqual(r['cumplimiento'], Decimal('100.00'))
        self.assertEqual(r['aporte'], Decimal('25.00'))

    def test_diez_de_diez_tope_120(self):
        item = SimpleNamespace(clase='PORC', meta_original=Decimal('0.8'), ponderacion=Decimal('25'))
        m = SimpleNamespace(item=item, estado='VAL', resueltos=10, recibidos=10)
        r = calcular_especial(m)
        self.assertEqual(r['cumplimiento'], Decimal('120.00'))
        self.assertEqual(r['aporte'], Decimal('30.00'))

    def test_borrador_sin_puntos(self):
        item = SimpleNamespace(clase='PORC', meta_original=Decimal('0.8'), ponderacion=Decimal('25'))
        m = SimpleNamespace(item=item, estado='BOR', resueltos=10, recibidos=10)
        self.assertIsNone(calcular_especial(m)['aporte'])

    def test_variable_valida(self):
        item = SimpleNamespace(clase='DIN', meta_original=None, ponderacion=Decimal('5'))
        m = SimpleNamespace(item=item, estado='VAL', objetivo_variable=Decimal('12'),
                            realizado_variable=Decimal('6'))
        r = calcular_especial(m)
        self.assertEqual(r['cumplimiento'], Decimal('50.00'))
        self.assertEqual(r['aporte'], Decimal('2.50'))

    def test_sin_objetivo_variable_no_puntua(self):
        item = SimpleNamespace(clase='DIN', meta_original=None, ponderacion=Decimal('5'))
        m = SimpleNamespace(item=item, estado='VAL', objetivo_variable=None, realizado_variable=Decimal('6'))
        self.assertIsNone(calcular_especial(m)['cumplimiento'])

    def test_felicitacion_no_puntua_automaticamente(self):
        item = SimpleNamespace(clase='ESP', meta_original=None, ponderacion=Decimal('10'))
        m = SimpleNamespace(item=item, estado='VAL')
        self.assertIsNone(calcular_especial(m)['aporte'])

    def test_validar_no_puede_contar_mas_resueltos_que_recibidos(self):
        item = ItemMatrizSGR(pk=123, clase='PORC', meta_original=Decimal('0.8'),
                             ponderacion=Decimal('25'))
        m = MedicionEspecialSGR(item=item, resueltos=11, recibidos=10, estado='BOR')
        with self.assertRaises(ValidationError) as error:
            m.clean()
        self.assertIn('resueltos', error.exception.message_dict)
