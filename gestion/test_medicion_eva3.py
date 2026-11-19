"""Pruebas de cálculo, aislamientos por cargo y autorizaciones del módulo de medición."""
from datetime import date, timedelta
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from catalogos.models import Cargo
from delegaciones.models import Delegacion
from funcionarios.models import Funcionario
from .medicion_eva3_calculos import contar_habiles, calcular_resumen_meta
from .models import (Actividad, Periodo, MetaIndicador, ActividadIndicador,
                     ConfiguracionMetaSGR, AusenciaSGR)


class MedicionEVA3Tests(TestCase):
    @classmethod
    def setUpTestData(cls):
        U = get_user_model()
        cls.admin = U.objects.create_user(username="admin_fase3", password="ClaveSegura123!", rol="ADMIN")
        cls.usuario = U.objects.create_user(username="func_fase3", password="ClaveSegura123!", rol="FUNC")
        cls.delegado = U.objects.create_user(username="deleg_fase3", password="ClaveSegura123!", rol="DELEG")
        cls.otra = U.objects.create_user(username="otro_fase3", password="ClaveSegura123!", rol="FUNC")
        cls.delegacion = Delegacion.objects.create(nombre="Delegación Fase 3")
        cls.otra_delegacion = Delegacion.objects.create(nombre="Otra Fase 3")
        cls.cargo = Cargo.objects.create(nombre_cargo="Gestor Fase 3")
        cls.funcionario = Funcionario.objects.create(delegacion=cls.delegacion, cargo=cls.cargo, rut="10000013-K", nombre="Funcionaria prueba", email="gestorfase3@example.test", usuario=cls.usuario)
        cls.jefe = Funcionario.objects.create(delegacion=cls.delegacion, cargo=cls.cargo, rut="12345678-5", nombre="Delegado prueba", email="delegadofase3@example.test", usuario=cls.delegado)
        cls.ajeno = Funcionario.objects.create(delegacion=cls.otra_delegacion, cargo=cls.cargo, rut="11111111-1", nombre="Otro funcionario", email="otrofase3@example.test", usuario=cls.otra)
        hoy = timezone.localdate()
        cls.periodo = Periodo.objects.create(nombre="Periodo Fase3", fecha_inicio=hoy-timedelta(days=10), fecha_fin=hoy+timedelta(days=20))
        cls.meta = MetaIndicador.objects.create(nombre="Meta prueba", delegacion=cls.delegacion, periodo=cls.periodo, meta_cantidad=2, ponderacion=50)

    def _actividad(self, empleado=None):
        empleado = empleado or self.funcionario
        return Actividad.objects.create(
            funcionario=empleado, delegacion=empleado.delegacion, fecha_actividad=timezone.localdate(),
            titulo="Taller realizado", accion_realizada="Se realizó el taller", tipo_accion=Actividad.TipoAccion.EJECUTADA,
            estado=Actividad.Estado.APROBADA, nombre_solicitante="Vecino de prueba",
            telefono_solicitante="987654321", creado_por=self.admin,
        )

    def test_habiles_sin_fines_de_semana(self):
        self.assertEqual(contar_habiles(date(2026, 11, 9), date(2026, 11, 15)), 5)
        self.assertEqual(contar_habiles(date(2026, 11, 14), date(2026, 11, 15)), 0)

    def test_calculo_inicial_y_tope(self):
        a = self._actividad()
        ActividadIndicador.objects.create(actividad=a, meta=self.meta, asignado_por=self.admin)
        r = calcular_resumen_meta(self.meta)
        self.assertEqual(r["cantidad"], 1)
        self.assertEqual(r["porcentaje"], Decimal("50.00"))
        self.assertEqual(r["aporte_ponderado"], Decimal("25.00"))
        ConfiguracionMetaSGR.objects.create(meta=self.meta, funcionario=self.funcionario, tope_porcentaje=Decimal("120"))
        # Permite más del 100% pero nunca supera el límite configurado.
        b = self._actividad()
        ActividadIndicador.objects.create(actividad=b, meta=self.meta, asignado_por=self.admin)
        self.assertLessEqual(calcular_resumen_meta(self.meta)["porcentaje"], Decimal("120.00"))

    def test_asignacion_de_otro_funcionario_no_suma(self):
        ConfiguracionMetaSGR.objects.create(meta=self.meta, funcionario=self.funcionario)
        a = self._actividad(empleado=self.jefe)
        ActividadIndicador.objects.create(actividad=a, meta=self.meta, asignado_por=self.admin)
        self.assertEqual(calcular_resumen_meta(self.meta)["cantidad"], 0)

    def test_ausencias_disminuyen_meta_ajustada(self):
        ConfiguracionMetaSGR.objects.create(meta=self.meta, funcionario=self.funcionario)
        antes = calcular_resumen_meta(self.meta)["meta_ajustada"]
        fecha = self.periodo.fecha_inicio
        while fecha.weekday() >= 5:
            fecha += timedelta(days=1)
        AusenciaSGR.objects.create(funcionario=self.funcionario, periodo=self.periodo, tipo="VAC", fecha_inicio=fecha, fecha_fin=fecha, registrado_por=self.admin)
        despues = calcular_resumen_meta(self.meta)["meta_ajustada"]
        self.assertLess(despues, antes)

    def test_ausencia_solo_administrador_o_delegado(self):
        self.client.force_login(self.usuario)
        self.assertEqual(self.client.get(reverse("gestion:registrar_ausencia_sgr")).status_code, 403)
        self.client.force_login(self.delegado)
        self.assertEqual(self.client.get(reverse("gestion:registrar_ausencia_sgr")).status_code, 200)

    def test_no_accede_a_otra_delegacion(self):
        self.client.force_login(self.delegado)
        self.assertEqual(self.client.get(reverse("gestion:configurar_meta_sgr", args=[self.meta.pk])).status_code, 200)
        meta_ajena = MetaIndicador.objects.create(nombre="Otra meta", delegacion=self.otra_delegacion, periodo=self.periodo, meta_cantidad=5)
        self.assertEqual(self.client.get(reverse("gestion:configurar_meta_sgr", args=[meta_ajena.pk])).status_code, 404)
