"""Regresiones del validador: sin MariaDB ni migraciones."""
from django.core.exceptions import ValidationError
from django.test import SimpleTestCase
from .rut import normalizar_rut


class ValidacionRutTests(SimpleTestCase):
    def test_rut_con_puntos_y_guion(self):
        self.assertEqual(normalizar_rut('12.345.678-5'), '12345678-5')

    def test_rut_sin_puntos(self):
        self.assertEqual(normalizar_rut('12345678-5'), '12345678-5')

    def test_rut_sin_separadores(self):
        self.assertEqual(normalizar_rut('123456785'), '12345678-5')

    def test_rut_con_espacios(self):
        self.assertEqual(normalizar_rut('  12.345.678 - 5 '), '12345678-5')

    def test_digito_k_minuscula(self):
        self.assertEqual(normalizar_rut('1.000.005-k'), '1000005-K')

    def test_rut_ficticio_valido(self):
        self.assertEqual(normalizar_rut('99.999.998-0'), '99999998-0')

    def test_dv_incorrecto(self):
        with self.assertRaises(ValidationError):
            normalizar_rut('12.345.678-4')

    def test_invalido(self):
        with self.assertRaises(ValidationError):
            normalizar_rut('abc-123')
