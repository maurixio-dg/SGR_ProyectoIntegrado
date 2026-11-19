"""Pruebas Django de la fase 2; ejecutarlas con python manage.py test gestion.test_operativa_eva3."""
from datetime import timedelta
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from catalogos.models import Cargo
from delegaciones.models import Delegacion
from funcionarios.models import Funcionario
from .models import (Actividad, Periodo, AgendaCompromiso,
                     MetaIndicador, ActividadIndicador)
from .operativa_eva3 import _resumen_meta


class GestionOperativaEVA3Tests(TestCase):
    @classmethod
    def setUpTestData(cls):
        usuarios = get_user_model()
        cls.admin = usuarios.objects.create_user(username="admin_fase2", password="ClavePrueba123!", rol="ADMIN")
        cls.func1 = usuarios.objects.create_user(username="func_fase2", password="ClavePrueba123!", rol="FUNC")
        cls.func2 = usuarios.objects.create_user(username="func2_fase2", password="ClavePrueba123!", rol="FUNC")
        cls.deleg = Delegacion.objects.create(nombre="Delegación Fase 2")
        cls.otra_deleg = Delegacion.objects.create(nombre="Otra Delegación Fase 2")
        cls.cargo = Cargo.objects.create(nombre_cargo="Gestor Fase2")
        cls.empleado = Funcionario.objects.create(delegacion=cls.deleg, cargo=cls.cargo, rut="12345678-5", nombre="Gestor Uno", email="func1fase2@example.test", usuario=cls.func1)
        cls.otro_empleado = Funcionario.objects.create(delegacion=cls.otra_deleg, cargo=cls.cargo, rut="11111111-1", nombre="Gestor Dos", email="func2fase2@example.test", usuario=cls.func2)
        hoy = timezone.localdate()
        cls.periodo = Periodo.objects.create(nombre="Período Fase 2", fecha_inicio=hoy-timedelta(days=3), fecha_fin=hoy+timedelta(days=30))

    def _agenda(self, empleado=None, deleg=None):
        empleado = empleado or self.empleado
        deleg = deleg or self.deleg
        return AgendaCompromiso.objects.create(
            titulo="Reunión comunitaria", fecha=timezone.localdate()+timedelta(days=1),
            delegacion=deleg, responsable=empleado, creado_por=self.admin,
        )

    def _actividad(self, **extras):
        datos = dict(
            fecha_actividad=timezone.localdate(), delegacion=self.deleg,
            funcionario=self.empleado, titulo="Atención ejecutada",
            tipo_accion=Actividad.TipoAccion.EJECUTADA, estado=Actividad.Estado.APROBADA,
            accion_realizada="Se prestó atención", nombre_solicitante="Vecino prueba",
            telefono_solicitante="912345678", creado_por=self.func1,
        )
        datos.update(extras)
        return Actividad.objects.create(**datos)

    def test_crud_agenda_admin(self):
        self.client.force_login(self.admin)
        url = reverse("gestion:nuevo_compromiso")
        response = self.client.post(url, {
            "titulo":"Operativo municipal", "fecha": (timezone.localdate()+timedelta(days=1)).isoformat(),
            "delegacion":self.deleg.pk, "responsable":self.empleado.pk,
            "estado":AgendaCompromiso.Estado.PLANIFICADO,
        })
        self.assertEqual(response.status_code, 302, response.context and response.context.get('formulario'))
        self.assertTrue(AgendaCompromiso.objects.filter(titulo="Operativo municipal").exists())

    def test_agenda_no_visible_otra_delegacion(self):
        ajeno = self._agenda(empleado=self.otro_empleado, deleg=self.otra_deleg)
        self.client.force_login(self.func1)
        response = self.client.get(reverse("gestion:detalle_compromiso", args=[ajeno.codigo]))
        self.assertEqual(response.status_code, 404)

    def test_agenda_eliminacion_requiere_post(self):
        c = self._agenda()
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(reverse("gestion:eliminar_compromiso", args=[c.pk])).status_code, 405)
        self.assertEqual(self.client.post(reverse("gestion:eliminar_compromiso", args=[c.pk])).status_code, 302)
        self.assertFalse(AgendaCompromiso.objects.filter(pk=c.pk).exists())

    def test_indicador_cuenta_solo_asignadas_elegibles(self):
        meta = MetaIndicador.objects.create(nombre="Atenciones", delegacion=self.deleg, periodo=self.periodo, meta_cantidad=2, ponderacion=50)
        buena = self._actividad()
        mala = self._actividad(nombre_solicitante="")
        extra = self._actividad()
        ActividadIndicador.objects.create(actividad=buena, meta=meta, asignado_por=self.admin)
        ActividadIndicador.objects.create(actividad=mala, meta=meta, asignado_por=self.admin)
        resumen = _resumen_meta(meta)
        self.assertEqual(resumen["cantidad"], 1)  # extra no asignada no cuenta
        self.assertEqual(resumen["porcentaje"], 50)
        self.assertEqual(resumen["aporte_ponderado"], 25)

    def test_meta_tope_120(self):
        meta = MetaIndicador.objects.create(nombre="Gestiones", delegacion=self.deleg, periodo=self.periodo, meta_cantidad=1)
        for idx in range(2):
            act = self._actividad(titulo=f"Atención {idx}")
            ActividadIndicador.objects.create(actividad=act, meta=meta, asignado_por=self.admin)
        self.assertEqual(_resumen_meta(meta)["porcentaje"], 120)

    def test_exportacion_privacidad_y_csv_seguro(self):
        self._actividad(titulo="=SUSPICIOSO(1)")
        self.client.force_login(self.func2)
        r = self.client.get(reverse("gestion:exportar_informe_csv"))
        self.assertEqual(r.status_code, 200)
        self.assertNotIn("SUSPICIOSO", r.content.decode("utf-8"))
        self.client.force_login(self.admin)
        r = self.client.get(reverse("gestion:exportar_informe_csv"))
        self.assertIn("'=SUSPICIOSO", r.content.decode("utf-8"))

    def test_validacion_permisos(self):
        actividad = self._actividad(estado=Actividad.Estado.REGISTRADA)
        self.client.force_login(self.func1)
        url = reverse("gestion:resolver_actividad", args=[actividad.pk])
        self.assertEqual(self.client.post(url, {"decision":"APR"}).status_code, 403)
        self.client.force_login(self.admin)
        r = self.client.post(url, {"decision":"APR", "observacion":"Validada"})
        self.assertEqual(r.status_code, 302)
        actividad.refresh_from_db()
        self.assertEqual(actividad.estado, Actividad.Estado.APROBADA)
        self.assertEqual(actividad.revisiones_eva3.count(), 1)

    def test_no_autenticado_restringido(self):
        for nombre in ("gestion:agenda_colectiva", "gestion:indicadores", "gestion:informes_gestion"):
            self.assertEqual(self.client.get(reverse(nombre)).status_code, 302)
