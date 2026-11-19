from datetime import timedelta
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from catalogos.models import Cargo
from delegaciones.models import Delegacion
from funcionarios.models import Funcionario
from gestion.models import Actividad


class ActividadesEva3Tests(TestCase):
    @classmethod
    def setUpTestData(cls):
        usuario = get_user_model()
        cls.admin = usuario.objects.create_user(
            username="admin_test_eva3", password="ClaveSegura.Pruebas123", rol="ADMIN"
        )
        cls.func_usuario = usuario.objects.create_user(
            username="func_test_eva3", password="ClaveSegura.Pruebas123", rol="FUNC"
        )
        cls.delegacion = Delegacion.objects.create(nombre="Delegación Test EVA3")
        cls.cargo = Cargo.objects.create(nombre_cargo="Gestor Test EVA3")
        cls.funcionario = Funcionario.objects.create(
            delegacion=cls.delegacion, cargo=cls.cargo,
            rut="12345678-5", nombre="Funcionario Prueba",
            email="func_eva3@example.test", usuario=cls.func_usuario,
        )

    def datos(self, **extra):
        valores = {
            "fecha_actividad": timezone.localdate(),
            "delegacion": self.delegacion,
            "funcionario": self.funcionario,
            "tipo_accion": Actividad.TipoAccion.EJECUTADA,
            "titulo": "Atención comunitaria",
            "accion_realizada": "Se realizó atención en terreno",
            "nombre_solicitante": "Vecino de prueba",
            "telefono_solicitante": "912345678",
            "creado_por": self.func_usuario,
        }
        valores.update(extra)
        return valores

    def test_limite_7_actividades_diarias(self):
        for i in range(7):
            actividad = Actividad(**self.datos(titulo=f"Actividad {i + 1}"))
            actividad.full_clean()
            actividad.save()
        octava = Actividad(**self.datos(titulo="Octava actividad"))
        with self.assertRaises(ValidationError):
            octava.full_clean()

    def test_sin_contacto_no_eligible_para_puntaje(self):
        a = Actividad(**self.datos(nombre_solicitante="", estado=Actividad.Estado.APROBADA))
        self.assertFalse(a.elegible_para_puntaje)

    def test_coordinacion_no_eligible_para_puntaje(self):
        a = Actividad(**self.datos(tipo_accion=Actividad.TipoAccion.COORDINACION, estado=Actividad.Estado.APROBADA))
        self.assertFalse(a.elegible_para_puntaje)

    def test_delegado_solicitante_no_eligible_para_puntaje(self):
        a = Actividad(**self.datos(solicitante_es_delegado=True, estado=Actividad.Estado.APROBADA))
        self.assertFalse(a.elegible_para_puntaje)

    def test_no_permite_actividad_futura(self):
        a = Actividad(**self.datos(fecha_actividad=timezone.localdate() + timedelta(days=1)))
        with self.assertRaises(ValidationError):
            a.full_clean()

    def test_formulario_crea_actividad_en_mariadb(self):
        self.client.force_login(self.func_usuario)
        respuesta = self.client.post(reverse("gestion:registrar_actividad"), {
            "fecha_actividad": timezone.localdate().isoformat(),
            "delegacion": self.delegacion.pk,
            "funcionario": self.funcionario.pk,
            "tipo_accion": Actividad.TipoAccion.EJECUTADA,
            "titulo": "Actividad real de prueba",
            "accion_realizada": "Atención realizada",
            "nombre_solicitante": "Solicitante de prueba",
            "telefono_solicitante": "912345678",
        })
        self.assertEqual(respuesta.status_code, 302, respuesta.context and respuesta.context.get("formulario"))
        self.assertEqual(Actividad.objects.count(), 1)

    def test_listado_requiere_autenticacion(self):
        respuesta = self.client.get(reverse("gestion:listar_actividades"))
        self.assertEqual(respuesta.status_code, 302)
