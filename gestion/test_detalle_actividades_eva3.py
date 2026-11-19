"""Pruebas de lectura y bloqueo de actividades aprobadas — Fase 5.2.
Ejecutar: python manage.py test gestion.test_detalle_actividades_eva3
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from catalogos.models import Cargo
from delegaciones.models import Delegacion
from funcionarios.models import Funcionario
from gestion.models import Actividad, ActividadIndicador


class DetalleActividadesEva3Tests(TestCase):
    @classmethod
    def setUpTestData(cls):
        Usuario = get_user_model()
        cls.admin = Usuario.objects.create_user(username="admin_detalle_eva3", password="PruebaSegura.123", rol="ADMIN")
        cls.usuario = Usuario.objects.create_user(username="func_detalle_eva3", password="PruebaSegura.123", rol="FUNC")
        cls.ajeno = Usuario.objects.create_user(username="ajeno_detalle_eva3", password="PruebaSegura.123", rol="FUNC")
        cls.delegacion = Delegacion.objects.create(nombre="Delegación Detalle EVA3")
        cls.otra_delegacion = Delegacion.objects.create(nombre="Delegación Externa EVA3")
        cls.cargo = Cargo.objects.create(nombre_cargo="Cargo Detalle EVA3")
        cls.funcionario = Funcionario.objects.create(
            delegacion=cls.delegacion, cargo=cls.cargo, rut="12345678-5",
            nombre="Funcionario Detalle", email="func_detalle@example.test", usuario=cls.usuario,
        )
        cls.funcionario_ajeno = Funcionario.objects.create(
            delegacion=cls.otra_delegacion, cargo=cls.cargo, rut="11111111-1",
            nombre="Funcionario Externo", email="ajeno_detalle@example.test", usuario=cls.ajeno,
        )
        cls.aprobada = Actividad.objects.create(
            fecha_actividad=timezone.localdate(), delegacion=cls.delegacion,
            funcionario=cls.funcionario, tipo_accion=Actividad.TipoAccion.EJECUTADA,
            titulo="Actividad aprobada de prueba", descripcion="Detalle reservado",
            accion_realizada="Atención efectiva", nombre_solicitante="Solicitante demo",
            telefono_solicitante="912345678", estado=Actividad.Estado.APROBADA,
            creado_por=cls.usuario,
        )
        cls.registrada = Actividad.objects.create(
            fecha_actividad=timezone.localdate(), delegacion=cls.delegacion,
            funcionario=cls.funcionario, tipo_accion=Actividad.TipoAccion.EJECUTADA,
            titulo="Actividad registrada de prueba", accion_realizada="Atención registrada",
            estado=Actividad.Estado.REGISTRADA, creado_por=cls.usuario,
        )

    def test_admin_consulta_actividad_aprobada(self):
        self.client.force_login(self.admin)
        respuesta = self.client.get(reverse("gestion:detalle_actividad", args=[self.aprobada.pk]))
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Actividad aprobada de prueba")
        self.assertContains(respuesta, "Sin asignación")
        self.assertNotContains(respuesta, reverse("gestion:editar_actividad", args=[self.aprobada.pk]))

    def test_ruta_antigua_redirige_a_detalle_sin_403(self):
        self.client.force_login(self.admin)
        respuesta = self.client.get(reverse("gestion:editar_actividad", args=[self.aprobada.pk]))
        self.assertRedirects(respuesta, reverse("gestion:detalle_actividad", args=[self.aprobada.pk]))

    def test_post_actividad_aprobada_continua_prohibido(self):
        self.client.force_login(self.admin)
        respuesta = self.client.post(reverse("gestion:editar_actividad", args=[self.aprobada.pk]), {
            "titulo": "Intento de modificación", "fecha_actividad": timezone.localdate().isoformat()
        })
        self.assertEqual(respuesta.status_code, 403)
        self.aprobada.refresh_from_db()
        self.assertEqual(self.aprobada.titulo, "Actividad aprobada de prueba")

    def test_el_funcionario_puede_consultar_su_aprobada(self):
        self.client.force_login(self.usuario)
        respuesta = self.client.get(reverse("gestion:detalle_actividad", args=[self.aprobada.pk]))
        self.assertEqual(respuesta.status_code, 200)

    def test_funcionario_ajeno_no_puede_consultar(self):
        self.client.force_login(self.ajeno)
        respuesta = self.client.get(reverse("gestion:detalle_actividad", args=[self.aprobada.pk]))
        self.assertEqual(respuesta.status_code, 404)

    def test_editar_registrada_sigue_funcionando(self):
        self.client.force_login(self.usuario)
        respuesta = self.client.get(reverse("gestion:editar_actividad", args=[self.registrada.pk]))
        self.assertEqual(respuesta.status_code, 200)

    def test_listado_muestra_accion_segun_permiso_y_estado(self):
        self.client.force_login(self.usuario)
        respuesta = self.client.get(reverse("gestion:listar_actividades"))
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Ver detalle")
        self.assertContains(respuesta, ">Editar<")

    def test_detalle_post_no_permitido(self):
        self.client.force_login(self.admin)
        respuesta = self.client.post(reverse("gestion:detalle_actividad", args=[self.aprobada.pk]), {})
        self.assertEqual(respuesta.status_code, 405)
