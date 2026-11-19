"""Pruebas de información real, ausencia de valores ficticios y ámbito de acceso."""
from datetime import timedelta
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from catalogos.models import Cargo
from delegaciones.models import Delegacion
from funcionarios.models import Funcionario
from gestion.models import Actividad, AgendaCompromiso, MetaIndicador, Periodo


class DashboardEva3Tests(TestCase):
    @classmethod
    def setUpTestData(cls):
        U = get_user_model()
        cls.admin = U.objects.create_user(username="admin_dashboard_eva3", password="PruebaSegura123!", rol="ADMIN")
        cls.func = U.objects.create_user(username="func_dashboard_eva3", password="PruebaSegura123!", rol="FUNC")
        cls.ajeno = U.objects.create_user(username="otro_dashboard_eva3", password="PruebaSegura123!", rol="FUNC")
        cls.delegacion = Delegacion.objects.create(nombre="Delegación Dashboard Norte")
        cls.otra_delegacion = Delegacion.objects.create(nombre="Delegación Dashboard Sur")
        cls.cargo = Cargo.objects.create(nombre_cargo="Cargo Dashboard")
        cls.funcionario = Funcionario.objects.create(
            delegacion=cls.delegacion, cargo=cls.cargo, rut="12345678-5",
            nombre="Funcionario Dashboard", email="dashboard1@example.test", usuario=cls.func,
        )
        cls.otro_funcionario = Funcionario.objects.create(
            delegacion=cls.otra_delegacion, cargo=cls.cargo, rut="10000013-K",
            nombre="Otro Dashboard", email="dashboard2@example.test", usuario=cls.ajeno,
        )
        hoy = timezone.localdate()
        cls.periodo = Periodo.objects.create(
            nombre="Periodo Dashboard EVA3", fecha_inicio=hoy-timedelta(days=15),
            fecha_fin=hoy+timedelta(days=15),
        )
        cls.meta = MetaIndicador.objects.create(
            nombre="Meta Dashboard", delegacion=cls.delegacion,
            periodo=cls.periodo, meta_cantidad=5, ponderacion=100,
        )
        cls.actividad = Actividad.objects.create(
            titulo="Actividad Dashboard", accion_realizada="Actividad ejecutada",
            fecha_actividad=hoy, delegacion=cls.delegacion,
            funcionario=cls.funcionario, creado_por=cls.func,
        )
        cls.compromiso = AgendaCompromiso.objects.create(
            titulo="Compromiso Dashboard", fecha=hoy,
            delegacion=cls.delegacion, responsable=cls.funcionario,
            creado_por=cls.admin,
        )
        Actividad.objects.create(
            titulo="Actividad de otra delegación", accion_realizada="Otra gestión",
            fecha_actividad=hoy, delegacion=cls.otra_delegacion,
            funcionario=cls.otro_funcionario, creado_por=cls.ajeno,
        )

    def test_administrador_ve_totales_reales(self):
        self.client.force_login(self.admin)
        respuesta = self.client.get(reverse("gestion:dashboard"))
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.context["total_delegaciones"], 2)
        self.assertEqual(respuesta.context["total_funcionarios"], 2)
        self.assertEqual(respuesta.context["total_actividades"], 2)
        self.assertEqual(respuesta.context["total_compromisos"], 1)
        self.assertEqual(respuesta.context["total_indicadores"], 1)
        self.assertEqual(str(respuesta.context["cumplimiento_metas"]), "0.0")
        self.assertNotContains(respuesta, "Datos ficticios")
        self.assertNotContains(respuesta, "de ejemplo")

    def test_funcionario_ve_sus_registros_sin_datos_ajenos(self):
        self.client.force_login(self.func)
        respuesta = self.client.get(reverse("gestion:dashboard"))
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.context["total_delegaciones"], 1)
        self.assertEqual(respuesta.context["total_funcionarios"], 1)
        self.assertEqual(respuesta.context["total_actividades"], 1)
        self.assertEqual(respuesta.context["total_compromisos"], 1)
        self.assertNotContains(respuesta, "Actividad de otra delegación")

    def test_sin_metas_no_inventa_porcentaje(self):
        MetaIndicador.objects.all().delete()
        self.client.force_login(self.admin)
        respuesta = self.client.get(reverse("gestion:dashboard"))
        self.assertEqual(respuesta.status_code, 200)
        self.assertFalse(respuesta.context["hay_metas"])
        self.assertIsNone(respuesta.context["cumplimiento_metas"])
        self.assertContains(respuesta, "—")

    def test_dashboard_exige_sesion(self):
        respuesta = self.client.get(reverse("gestion:dashboard"))
        self.assertEqual(respuesta.status_code, 302)
