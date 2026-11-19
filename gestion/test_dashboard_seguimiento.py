"""Pruebas del panel por rol y filtros seguros. Ejecución: manage.py test gestion.test_dashboard_seguimiento"""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from catalogos.models import Cargo
from delegaciones.models import Delegacion
from funcionarios.models import Funcionario
from gestion.models import Actividad, MetaIndicador, Periodo
from gestion.medicion_eva3_models import ConfiguracionMetaSGR


class PanelSeguimientoTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        U = get_user_model()
        cls.admin = U.objects.create_user(username="panel_admin", password="Test-Panel-123!", rol="ADMIN")
        cls.a = U.objects.create_user(username="panel_a", password="Test-Panel-123!", rol="FUNC")
        cls.b = U.objects.create_user(username="panel_b", password="Test-Panel-123!", rol="FUNC")
        cls.jefe = U.objects.create_user(username="panel_jefe", password="Test-Panel-123!", rol="DELEG")
        cls.c = U.objects.create_user(username="panel_c", password="Test-Panel-123!", rol="FUNC")
        cls.norte = Delegacion.objects.create(nombre="Panel Norte")
        cls.sur = Delegacion.objects.create(nombre="Panel Sur")
        cls.cargo = Cargo.objects.create(nombre_cargo="Cargo panel")
        def funcionario(nombre, rut, usuario, delegacion):
            return Funcionario.objects.create(nombre=nombre, rut=rut,
                email=f"{usuario.username}@example.test", delegacion=delegacion, cargo=cls.cargo, usuario=usuario)
        cls.fa = funcionario("Funcionario A", "10000001-9", cls.a, cls.norte)
        cls.fb = funcionario("Funcionario B", "10000002-7", cls.b, cls.norte)
        cls.fj = funcionario("Jefatura Norte", "10000003-5", cls.jefe, cls.norte)
        cls.fc = funcionario("Funcionario C", "10000004-3", cls.c, cls.sur)
        hoy = timezone.localdate()
        cls.periodo = Periodo.objects.create(nombre="Panel periodo", fecha_inicio=hoy-timedelta(days=30), fecha_fin=hoy+timedelta(days=10))
        cls.meta_personal = MetaIndicador.objects.create(nombre="Meta de A", delegacion=cls.norte,
            periodo=cls.periodo, meta_cantidad=10, ponderacion=40)
        ConfiguracionMetaSGR.objects.create(meta=cls.meta_personal, funcionario=cls.fa)
        cls.meta_colectiva = MetaIndicador.objects.create(nombre="Meta global norte", delegacion=cls.norte,
            periodo=cls.periodo, meta_cantidad=10, ponderacion=60)
        def actividad(nombre, f, user, estado=Actividad.Estado.REGISTRADA):
            return Actividad.objects.create(titulo=nombre, accion_realizada="Prueba", fecha_actividad=hoy,
                delegacion=f.delegacion, funcionario=f, creado_por=user, estado=estado)
        actividad("Actividad A", cls.fa, cls.a, Actividad.Estado.APROBADA)
        actividad("Actividad B", cls.fb, cls.b)
        actividad("Actividad C privada", cls.fc, cls.c)

    def ver(self, usuario, params=None):
        self.client.force_login(usuario)
        return self.client.get(reverse("gestion:dashboard"), params or {})

    def test_administracion_ve_delegaciones_y_resumen_global(self):
        r = self.ver(self.admin)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.context["panel_total"], 3)
        self.assertEqual(len(r.context["panel_delegaciones"]), 2)
        self.assertContains(r, "Evolución de actividades")

    def test_usuario_solo_ve_su_actividad_y_no_nombre_ajeno(self):
        r = self.ver(self.a)
        self.assertEqual(r.context["panel_total"], 1)
        self.assertNotContains(r, "Actividad C privada")
        self.assertFalse(r.context["panel_puede_delegacion"])
        self.assertFalse(r.context["panel_puede_funcionario"])
        self.assertEqual(r.context["panel_metas_total"], 1)

    def test_usuario_no_amplia_acceso_con_get_manipulado(self):
        r = self.ver(self.a, {"delegacion": str(self.sur.pk), "funcionario": str(self.fc.pk)})
        self.assertEqual(r.context["panel_total"], 1)
        self.assertNotContains(r, "Funcionario C")

    def test_jefatura_ve_su_delegacion_y_filtra_funcionario(self):
        r = self.ver(self.jefe)
        self.assertEqual(r.context["panel_total"], 2)
        self.assertEqual(len(r.context["panel_funcionarios"]), 3)
        filtrado = self.ver(self.jefe, {"funcionario": str(self.fa.pk)})
        self.assertEqual(filtrado.context["panel_total"], 1)
        self.assertEqual(filtrado.context["panel_metas_total"], 1)
        self.assertIsNone(filtrado.context["panel_delegacion_id"])

    def test_jefatura_no_ve_otra_delegacion_aunque_la_pida(self):
        r = self.ver(self.jefe, {"delegacion": str(self.sur.pk), "funcionario": str(self.fc.pk)})
        self.assertEqual(r.context["panel_total"], 2)
        self.assertNotContains(r, "Actividad C privada")

    def test_admin_filtra_delegacion_y_empleado_sin_cruce(self):
        r = self.ver(self.admin, {"delegacion": str(self.norte.pk), "funcionario": str(self.fc.pk)})
        self.assertEqual(r.context["panel_total"], 2)
        self.assertIsNone(r.context["panel_funcionario_id"])
        r2 = self.ver(self.admin, {"delegacion": str(self.sur.pk)})
        self.assertEqual(r2.context["panel_total"], 1)
        self.assertEqual(r2.context["panel_aprobadas"], 0)

    def test_periodo_ajeno_vacio_sin_falsas_cifras(self):
        p = Periodo.objects.create(nombre="Periodo anterior", fecha_inicio=timezone.localdate()-timedelta(days=450),
            fecha_fin=timezone.localdate()-timedelta(days=400))
        r = self.ver(self.admin, {"periodo": str(p.pk)})
        self.assertEqual(r.context["panel_total"], 0)
        self.assertEqual(r.context["panel_metas_total"], 0)
        self.assertEqual(len(r.context["panel_tendencia"]), 6)
