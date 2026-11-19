from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

Usuario = get_user_model()


class AccesoTemporalTests(TestCase):
    def setUp(self):
        self.admin = Usuario.objects.create_superuser(username="admin_seguridad", password="ClaveAdminSegura!2026", email="admin@test.invalid")

    def crear_funcionario(self, username="func_prueba"):
        return Usuario.objects.create_user(username=username, password="TemporalSegura!2026", rol="FUNC")

    def test_creacion_solo_administrador_y_clave_no_se_guarda_en_texto_plano(self):
        self.client.force_login(self.admin)
        res = self.client.post(reverse("usuarios:crear"), {
            "username":"nueva_persona", "first_name":"Persona", "last_name":"SGR",
            "email":"nueva@test.invalid", "rol":"FUNC",
        })
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "Contraseña temporal generada")
        cuenta = Usuario.objects.get(username="nueva_persona")
        self.assertTrue(cuenta.debe_cambiar_password)
        self.assertNotIn("clave_temporal", cuenta.password.lower())
        self.assertTrue(cuenta.check_password(res.context["clave_temporal"]))
        self.assertIn("no-store", res["Cache-Control"])

    def test_no_superuser_no_puede_crear_cuenta(self):
        user = self.crear_funcionario()
        self.client.force_login(user)
        res = self.client.post(reverse("usuarios:crear"), {})
        self.assertEqual(res.status_code, 403)

    def test_usuarios_anteriores_no_se_obligan(self):
        user = self.crear_funcionario()
        self.assertFalse(user.debe_cambiar_password)
        self.client.force_login(user)
        res = self.client.get(reverse("gestion:dashboard"))
        self.assertNotEqual(res.status_code, 302)

    def test_primera_sesion_bloquea_dashboard_pero_no_cambio_password(self):
        user = self.crear_funcionario()
        user.debe_cambiar_password = True
        user.save(update_fields=["debe_cambiar_password"])
        self.client.force_login(user)
        res = self.client.get(reverse("gestion:dashboard"))
        self.assertRedirects(res, reverse("usuarios:cambiar_mi_password"), fetch_redirect_response=False)
        self.assertEqual(self.client.get(reverse("usuarios:cambiar_mi_password")).status_code, 200)
        self.assertEqual(self.client.get(reverse("usuarios:mi_perfil")).status_code, 302)

    def test_cambiar_temporal_conserva_sesion_y_desbloquea(self):
        user = self.crear_funcionario()
        user.debe_cambiar_password = True
        user.save(update_fields=["debe_cambiar_password"])
        self.client.force_login(user)
        res = self.client.post(reverse("usuarios:cambiar_mi_password"), {
            "old_password": "TemporalSegura!2026",
            "new_password1": "NuevaDefinitiva!2026",
            "new_password2": "NuevaDefinitiva!2026",
        })
        self.assertRedirects(res, reverse("gestion:dashboard"), fetch_redirect_response=False)
        user.refresh_from_db()
        self.assertFalse(user.debe_cambiar_password)
        self.assertTrue(user.check_password("NuevaDefinitiva!2026"))
        self.assertNotEqual(self.client.get(reverse("gestion:dashboard")).status_code, 302)

    def test_no_se_libera_con_password_incorrecta(self):
        user = self.crear_funcionario()
        user.debe_cambiar_password = True
        user.save(update_fields=["debe_cambiar_password"])
        self.client.force_login(user)
        res = self.client.post(reverse("usuarios:cambiar_mi_password"), {
            "old_password": "Incorrecta!2026",
            "new_password1": "NuevaDefinitiva!2026",
            "new_password2": "NuevaDefinitiva!2026",
        })
        self.assertEqual(res.status_code, 200)
        user.refresh_from_db()
        self.assertTrue(user.debe_cambiar_password)

    def test_reinicio_admin_invalida_password_previa(self):
        user = self.crear_funcionario()
        antigua = user.password
        self.client.force_login(self.admin)
        res = self.client.post(reverse("usuarios:reiniciar_password_temporal", kwargs={"pk":user.pk}))
        self.assertEqual(res.status_code, 200)
        user.refresh_from_db()
        self.assertTrue(user.debe_cambiar_password)
        self.assertNotEqual(antigua, user.password)
        self.assertTrue(user.check_password(res.context["clave_temporal"]))

    def test_reset_solo_por_post_y_no_superusuario(self):
        user = self.crear_funcionario()
        self.client.force_login(self.admin)
        url = reverse("usuarios:reiniciar_password_temporal", kwargs={"pk":user.pk})
        self.assertEqual(self.client.get(url).status_code, 405)
        self.assertEqual(self.client.post(reverse("usuarios:reiniciar_password_temporal", kwargs={"pk":self.admin.pk})).status_code, 404)
        self.client.force_login(user)
        self.assertEqual(self.client.post(url).status_code, 403)
