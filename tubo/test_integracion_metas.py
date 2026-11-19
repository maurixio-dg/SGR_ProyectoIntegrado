"""Pruebas de vinculación: sin doble puntuación, roles y reglas municipales."""
from datetime import timedelta
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from catalogos.models import Cargo
from delegaciones.models import Delegacion
from funcionarios.models import Funcionario
from gestion.medicion_eva3_calculos import calcular_resumen_meta
from gestion.models import Actividad, ActividadIndicador, MetaIndicador, Periodo
from .models import GestionSocial, TipoAtencion, Vecino, VinculoGestionActividad


class IntegracionTuboIndicadoresTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        usuarios = get_user_model()
        cls.admin = usuarios.objects.create_superuser(username='admin_integra_tubo', password='Prueba_12345!')
        cls.func = usuarios.objects.create_user(username='func_integra_tubo', password='Prueba_12345!', rol='FUNC')
        cls.delegado = usuarios.objects.create_user(username='delegado_integra_tubo', password='Prueba_12345!', rol='DELEG')
        cls.ajeno = usuarios.objects.create_user(username='ajeno_integra_tubo', password='Prueba_12345!', rol='DELEG')
        cls.d1 = Delegacion.objects.create(nombre='Delegación Integración A')
        cls.d2 = Delegacion.objects.create(nombre='Delegación Integración B')
        cargo = Cargo.objects.create(nombre_cargo='Gestor Integración')
        cls.f1 = Funcionario.objects.create(delegacion=cls.d1, cargo=cargo, rut='11111111-1', nombre='Gestor Uno', email='integracion_uno@example.test', usuario=cls.func)
        Funcionario.objects.create(delegacion=cls.d1, cargo=cargo, rut='22222222-2', nombre='Delegado Prueba', email='integracion_deleg@example.test', usuario=cls.delegado)
        Funcionario.objects.create(delegacion=cls.d2, cargo=cargo, rut='33333333-3', nombre='Delegado Ajeno', email='integracion_ajeno@example.test', usuario=cls.ajeno)
        cls.vecino = Vecino.objects.create(rut='44444444-4', nombre='Vecino de Prueba', telefono='987654321', delegacion=cls.d1, creado_por=cls.func)
        cls.tipo = TipoAtencion.objects.create(nombre='Atención Social Integración')
        hoy = timezone.localdate()
        cls.periodo = Periodo.objects.create(nombre='Período Integración', fecha_inicio=hoy-timedelta(days=5), fecha_fin=hoy+timedelta(days=10))
        cls.meta = MetaIndicador.objects.create(nombre='Acciones Resueltas', delegacion=cls.d1, periodo=cls.periodo, meta_cantidad=4, ponderacion=25)

    def _gestion(self, **attrs):
        kwargs = dict(delegacion=self.d1, vecino=self.vecino, tipo=self.tipo, responsable=self.f1,
                      titulo='Atención comunitaria completada', descripcion='Solicitud que culminó en acción ejecutada',
                      creado_por=self.func, estado=GestionSocial.Estado.APROBADA)
        kwargs.update(attrs)
        return GestionSocial.objects.create(**kwargs)

    def _nueva(self, gestion, **kwargs):
        datos = {'modo': 'nueva', 'meta': self.meta.pk,
                 'fecha_actividad': timezone.localdate().isoformat(),
                 'accion_realizada': 'Se completó la atención social requerida y se entregó solución.',
                 'confirmacion': 'on'}
        datos.update(kwargs)
        return self.client.post(reverse('tubo:vincular_meta', args=[gestion.pk]), datos)

    def _actividad(self, **kwargs):
        datos = dict(delegacion=self.d1, funcionario=self.f1, periodo=self.periodo,
                     fecha_actividad=timezone.localdate(),
                     titulo='Atención social completada',
                     tipo_accion=Actividad.TipoAccion.EJECUTADA,
                     accion_realizada='Se completó la acción acordada',
                     nombre_solicitante=self.vecino.nombre, telefono_solicitante=self.vecino.telefono,
                     estado=Actividad.Estado.APROBADA, creado_por=self.func)
        datos.update(kwargs)
        return Actividad.objects.create(**datos)

    def test_accion_nueva_contabiliza_una_vez(self):
        gestion = self._gestion()
        self.client.force_login(self.admin)
        respuesta = self._nueva(gestion)
        self.assertEqual(respuesta.status_code, 302)
        self.assertEqual(VinculoGestionActividad.objects.filter(gestion=gestion).count(), 1)
        self.assertEqual(Actividad.objects.filter(delegacion=self.d1).count(), 1)
        self.assertEqual(ActividadIndicador.objects.filter(meta=self.meta).count(), 1)
        self.assertEqual(calcular_resumen_meta(self.meta)['cantidad'], 1)
        self.assertEqual(calcular_resumen_meta(self.meta)['porcentaje'], 25)
        # Enlace visible y GET redirige, sin crear otro registro.
        self.assertContains(self.client.get(reverse('tubo:detalle_gestion', args=[gestion.pk])), 'SGR-ACT-')
        self.assertEqual(self._nueva(gestion).status_code, 302)
        self.assertEqual(Actividad.objects.filter(delegacion=self.d1).count(), 1)

    def test_asociar_existente_no_crea_otra_actividad_ni_doble_puntaje(self):
        gestion = self._gestion()
        actividad = self._actividad()
        ActividadIndicador.objects.create(actividad=actividad, meta=self.meta, asignado_por=self.admin)
        self.client.force_login(self.admin)
        response = self.client.post(reverse('tubo:vincular_meta', args=[gestion.pk]), {
            'modo': 'existente', 'meta': self.meta.pk, 'actividad_existente': actividad.pk})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Actividad.objects.filter(delegacion=self.d1).count(), 1)
        self.assertEqual(ActividadIndicador.objects.filter(meta=self.meta).count(), 1)
        self.assertEqual(calcular_resumen_meta(self.meta)['cantidad'], 1)
        self.assertEqual(VinculoGestionActividad.objects.get(gestion=gestion).actividad_id, actividad.pk)

    def test_actividad_ajena_al_vecino_no_se_puede_vincular(self):
        gestion = self._gestion()
        actividad = self._actividad(nombre_solicitante='Otra persona')
        self.client.force_login(self.admin)
        r = self.client.post(reverse('tubo:vincular_meta', args=[gestion.pk]), {
            'modo': 'existente', 'meta': self.meta.pk, 'actividad_existente': actividad.pk})
        self.assertEqual(r.status_code, 200)
        self.assertFalse(VinculoGestionActividad.objects.exists())
        self.assertFalse(ActividadIndicador.objects.exists())

    def test_delegado_puede_vincular_gestion_su_delegacion(self):
        gestion = self._gestion()
        self.client.force_login(self.delegado)
        r = self._nueva(gestion)
        self.assertEqual(r.status_code, 302)
        self.assertEqual(VinculoGestionActividad.objects.count(), 1)

    def test_gestion_no_aprobada_no_se_puede_vincular(self):
        gestion = self._gestion(estado=GestionSocial.Estado.PENDIENTE)
        self.client.force_login(self.admin)
        self.assertEqual(self._nueva(gestion).status_code, 403)
        self.assertFalse(Actividad.objects.exists())

    def test_solicitante_delegado_y_sin_telefono_no_puntuan(self):
        gestion = self._gestion(solicitante_es_delegado=True)
        self.client.force_login(self.admin)
        self.assertEqual(self._nueva(gestion).status_code, 200)
        self.assertFalse(VinculoGestionActividad.objects.exists())
        gestion.solicitante_es_delegado = False
        gestion.save(update_fields=['solicitante_es_delegado'])
        self.vecino.telefono = ''
        self.vecino.save(update_fields=['telefono'])
        self.assertEqual(self._nueva(gestion).status_code, 200)
        self.assertFalse(Actividad.objects.exists())

    def test_un_funcionario_no_puede_asignar_puntos(self):
        gestion = self._gestion()
        self.client.force_login(self.func)
        self.assertEqual(self._nueva(gestion).status_code, 403)
        self.assertFalse(Actividad.objects.exists())

    def test_funcionario_otra_delegacion_404(self):
        gestion = self._gestion()
        self.client.force_login(self.ajeno)
        self.assertEqual(self.client.get(reverse('tubo:vincular_meta', args=[gestion.pk])).status_code, 404)
        self.assertFalse(Actividad.objects.exists())

    def test_fecha_cerrada_y_tope_diario_protegidos(self):
        gestion = self._gestion()
        self.client.force_login(self.admin)
        r = self._nueva(gestion, fecha_actividad=(timezone.localdate()-timedelta(days=20)).isoformat())
        self.assertEqual(r.status_code, 200)
        self.assertEqual(VinculoGestionActividad.objects.count(), 0)
        for i in range(7):
            self._actividad(titulo=f'Acción {i}')
        r = self._nueva(gestion)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(Actividad.objects.count(), 7)

    def test_no_puede_asociar_actividad_delegada_a_otra_meta(self):
        gestion = self._gestion()
        actividad = self._actividad()
        otra = MetaIndicador.objects.create(nombre='Otra meta', delegacion=self.d1,
                                            periodo=self.periodo, meta_cantidad=5)
        ActividadIndicador.objects.create(actividad=actividad, meta=otra, asignado_por=self.admin)
        self.client.force_login(self.admin)
        r = self.client.post(reverse('tubo:vincular_meta', args=[gestion.pk]), {
            'modo': 'existente', 'meta': self.meta.pk, 'actividad_existente': actividad.pk})
        self.assertEqual(r.status_code, 200)
        self.assertFalse(VinculoGestionActividad.objects.exists())
        self.assertEqual(ActividadIndicador.objects.count(), 1)
