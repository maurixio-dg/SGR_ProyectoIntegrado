"""El enlace a mediciones especiales se muestra solo a quienes tienen acceso."""
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from catalogos.models import Cargo
from delegaciones.models import Delegacion
from funcionarios.models import Funcionario


class AccesoEnlaceMedicionesEspecialesTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        ModeloUsuario = get_user_model()
        cls.admin = ModeloUsuario.objects.create_superuser(
            username='admin_boton_matriz',
            email='admin_boton@example.invalid',
            password='ClaveFicticia-2026!',
        )
        cls.delegado = ModeloUsuario.objects.create_user(
            username='delegado_boton_matriz',
            password='ClaveFicticia-2026!',
            rol='DELEG',
        )
        delegacion = Delegacion.objects.create(nombre='Delegación de prueba de enlace')
        cargo = Cargo.objects.create(nombre_cargo='Delegado de prueba de enlace')
        Funcionario.objects.create(
            nombre='Delegado de prueba enlace',
            rut='12345678-5',
            email='delegado_boton@example.invalid',
            delegacion=delegacion,
            cargo=cargo,
            usuario=cls.delegado,
        )

    def test_administrador_ve_el_enlace_a_mediciones(self):
        self.client.force_login(self.admin)
        respuesta = self.client.get(reverse('matriz_sgr:valoraciones'))
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'href="' + reverse('matriz_sgr:especiales') + '"')

    def test_delegado_no_ve_el_enlace_sin_permiso(self):
        self.client.force_login(self.delegado)
        respuesta = self.client.get(reverse('matriz_sgr:valoraciones'))
        self.assertEqual(respuesta.status_code, 200)
        self.assertNotContains(respuesta, 'href="' + reverse('matriz_sgr:especiales') + '"')
        # La restricción del servidor permanece: ocultar el botón no concede acceso.
        respuesta_prohibida = self.client.get(reverse('matriz_sgr:especiales'))
        self.assertEqual(respuesta_prohibida.status_code, 403)
