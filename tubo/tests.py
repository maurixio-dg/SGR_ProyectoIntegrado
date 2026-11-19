from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from catalogos.models import Cargo
from delegaciones.models import Delegacion
from funcionarios.models import Funcionario
from .models import Vecino, TipoAtencion, SubtipoAtencion, GestionSocial, CartaTubo, normalizar_rut


class TuboSeguridadTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User=get_user_model()
        cls.d1=Delegacion.objects.create(nombre='Delegación uno')
        cls.d2=Delegacion.objects.create(nombre='Delegación dos')
        cargo=Cargo.objects.create(nombre_cargo='Gestor')
        cls.admin=User.objects.create_superuser(username='admin_tubo', password='TEST_Pass_123')
        cls.ana=User.objects.create_user(username='ana_tubo',password='TEST_Pass_123',rol='FUNC')
        cls.luis=User.objects.create_user(username='luis_tubo',password='TEST_Pass_123',rol='FUNC')
        cls.beto=User.objects.create_user(username='beto_tubo',password='TEST_Pass_123',rol='FUNC')
        cls.delegado=User.objects.create_user(username='delegado_tubo',password='TEST_Pass_123',rol='DELEG')
        cls.f1=Funcionario.objects.create(delegacion=cls.d1,cargo=cargo,rut='10101010-0',nombre='Ana',email='ana_tubo@example.test',usuario=cls.ana)
        cls.f2=Funcionario.objects.create(delegacion=cls.d1,cargo=cargo,rut='20202020-0',nombre='Luis',email='luis_tubo@example.test',usuario=cls.luis)
        cls.f3=Funcionario.objects.create(delegacion=cls.d2,cargo=cargo,rut='30303030-0',nombre='Beto',email='beto_tubo@example.test',usuario=cls.beto)
        Funcionario.objects.create(delegacion=cls.d1,cargo=cargo,rut='40404040-0',nombre='Delegado',email='del_tubo@example.test',usuario=cls.delegado)
        cls.tipo=TipoAtencion.objects.create(nombre='Atención social')
        cls.subtipo=SubtipoAtencion.objects.create(nombre='Ayuda',tipo=cls.tipo)
        cls.vecino1=Vecino.objects.create(rut='11111111-1',nombre='Vecina Uno',telefono='912345678',delegacion=cls.d1,creado_por=cls.ana)
        cls.vecino2=Vecino.objects.create(rut='22222222-2',nombre='Vecina Dos',telefono='987654321',delegacion=cls.d2,creado_por=cls.beto)
        cls.g1=GestionSocial.objects.create(delegacion=cls.d1,vecino=cls.vecino1,tipo=cls.tipo,
            subtipo=cls.subtipo,responsable=cls.f1,titulo='Solicitud vereda',descripcion='Reparar vereda de sector',creado_por=cls.ana)
        cls.g2=GestionSocial.objects.create(delegacion=cls.d2,vecino=cls.vecino2,tipo=cls.tipo,
            responsable=cls.f3,titulo='Solicitud alumbrado',descripcion='Reparar luminaria',creado_por=cls.beto)

    def test_rut_chileno(self):
        self.assertEqual(normalizar_rut('11.111.111-1'),'11111111-1')
        with self.assertRaises(ValidationError):
            normalizar_rut('11111111-9')

    def test_delegacion_aislada_incluido_detalle(self):
        self.client.force_login(self.ana)
        r=self.client.get(reverse('tubo:gestiones'))
        self.assertContains(r,'Solicitud vereda')
        self.assertNotContains(r,'Solicitud alumbrado')
        self.assertEqual(self.client.get(reverse('tubo:detalle_gestion',args=[self.g2.pk])).status_code,404)

    def test_funcionario_ve_registros_de_companero_sin_editar(self):
        self.client.force_login(self.luis)
        self.assertEqual(self.client.get(reverse('tubo:detalle_gestion',args=[self.g1.pk])).status_code,200)
        self.assertEqual(self.client.get(reverse('tubo:editar_gestion',args=[self.g1.pk])).status_code,302)
        respuesta=self.client.post(reverse('tubo:editar_gestion',args=[self.g1.pk]),{'titulo':'invalido'})
        self.assertEqual(respuesta.status_code,403)

    def test_aprobacion_bloquea_edicion_y_hitos(self):
        self.client.force_login(self.delegado)
        r=self.client.post(reverse('tubo:resolver_gestion',args=[self.g1.pk]),{'estado':'APR','comentario':'Aprobada con antecedentes'})
        self.assertEqual(r.status_code,302)
        self.g1.refresh_from_db()
        self.assertEqual(self.g1.estado,'APR')
        self.client.force_login(self.ana)
        self.assertEqual(self.client.get(reverse('tubo:detalle_gestion',args=[self.g1.pk])).status_code,200)
        self.assertEqual(self.client.post(reverse('tubo:editar_gestion',args=[self.g1.pk]),{'titulo':'invalido'}).status_code,403)
        self.assertEqual(self.client.post(reverse('tubo:hito_gestion',args=[self.g1.pk]),{'descripcion':'Hito posterior'}).status_code,403)

    def test_busqueda_codigo_nombre_rut_y_dinamica(self):
        self.client.force_login(self.ana)
        for q in [self.g1.codigo,'11111111-1','Vecina Uno']:
            self.assertContains(self.client.get(reverse('tubo:gestiones'),{'buscar':q}), 'Solicitud vereda')
        r=self.client.get(reverse('tubo:gestiones'),{'buscar':'Vecina Uno','live':'1'})
        self.assertEqual(r.status_code,200)
        self.assertIn('Solicitud vereda',r.json()['html'])

    def test_hito_registrado_e_historial(self):
        self.client.force_login(self.ana)
        self.assertEqual(self.client.post(reverse('tubo:hito_gestion',args=[self.g1.pk]),{
            'descripcion':'Se realizó llamada de coordinación'}).status_code,302)
        self.assertEqual(self.g1.hitos.count(),1)
        self.assertEqual(self.g1.historial.count(),1)

    def test_validacion_delegacion_otra(self):
        gestion=GestionSocial(delegacion=self.d1,vecino=self.vecino2,tipo=self.tipo,
            responsable=self.f1,titulo='Cruce no permitido',descripcion='Datos inconsistentes',creado_por=self.ana)
        with self.assertRaises(ValidationError):
            gestion.full_clean()

    def test_carta_permisos_y_cierre(self):
        carta=CartaTubo.objects.create(delegacion=self.d1,asunto='Oficio prueba',destinatario='Unidad',creado_por=self.ana)
        self.client.force_login(self.beto)
        self.assertEqual(self.client.get(reverse('tubo:detalle_carta',args=[carta.pk])).status_code,404)
        self.client.force_login(self.luis)
        self.assertEqual(self.client.get(reverse('tubo:detalle_carta',args=[carta.pk])).status_code,200)
        self.client.force_login(self.ana)
        carta.estado=CartaTubo.Estado.CERRADA
        carta.save()
        self.assertRedirects(self.client.get(reverse('tubo:editar_carta',args=[carta.pk])),reverse('tubo:detalle_carta',args=[carta.pk]))
        self.assertEqual(self.client.post(reverse('tubo:editar_carta',args=[carta.pk]),{'asunto':'Modificación prohibida'}).status_code,403)

    def test_consulta_sin_usuario_no_autoriza(self):
        r=self.client.get(reverse('tubo:gestiones'))
        self.assertEqual(r.status_code,302)

    def test_vecino_con_gestion_protegido_ante_eliminacion(self):
        self.client.force_login(self.admin)
        r=self.client.post(reverse('tubo:eliminar_vecino',args=[self.vecino1.pk]))
        self.assertEqual(r.status_code,302)
        self.assertTrue(Vecino.objects.filter(pk=self.vecino1.pk).exists())

    def test_catalogo_en_uso_no_puede_eliminarse(self):
        self.client.force_login(self.admin)
        r=self.client.post(reverse('tubo:eliminar_catalogo',args=['tipos',self.tipo.pk]))
        self.assertEqual(r.status_code,302)
        self.assertTrue(TipoAtencion.objects.filter(pk=self.tipo.pk).exists())

    def test_subtipos_dinamicos(self):
        self.client.force_login(self.ana)
        r=self.client.get(reverse('tubo:subtipos_por_tipo'),{'tipo':self.tipo.pk})
        self.assertEqual(r.status_code,200)
        self.assertEqual(r.json()['resultados'][0]['nombre'],'Ayuda')

    def test_crear_gestion_desde_formulario_y_que_no_puntue_automaticamente(self):
        self.client.force_login(self.ana)
        datos={
            'delegacion':self.d1.pk,'vecino':self.vecino1.pk,'tipo':self.tipo.pk,
            'subtipo':self.subtipo.pk,'responsable':self.f1.pk,
            'titulo':'Atención de prueba','descripcion':'Solicitud ingresada durante la prueba del sistema',
            'ingresa_tubo':'on',
        }
        response=self.client.post(reverse('tubo:nueva_gestion'),datos)
        self.assertEqual(response.status_code,302, response.context['formulario'].errors if response.context else response.content[:600])
        nueva=GestionSocial.objects.get(titulo='Atención de prueba')
        self.assertEqual(nueva.creado_por,self.ana)
        self.assertEqual(nueva.estado,GestionSocial.Estado.PENDIENTE)
        self.assertEqual(nueva.historial.count(),1)

    def test_formulario_rechaza_otro_territorio(self):
        self.client.force_login(self.ana)
        response=self.client.post(reverse('tubo:nueva_gestion'),{
            'delegacion':self.d1.pk,'vecino':self.vecino2.pk,'tipo':self.tipo.pk,
            'responsable':self.f1.pk,'titulo':'Datos cruzados',
            'descripcion':'Prueba de aislamiento de delegación',
        })
        self.assertEqual(response.status_code,200)
        self.assertFalse(GestionSocial.objects.filter(titulo='Datos cruzados').exists())

    def test_carta_se_crea_y_no_se_puede_asociar_gestion_ajena(self):
        self.client.force_login(self.ana)
        response=self.client.post(reverse('tubo:nueva_carta'),{
            'delegacion':self.d1.pk,'asunto':'Respuesta formal','destinatario':'Vecina Uno',
            'numero_oficio':'01-2026','descripcion':'Remisión de antecedentes','estado':'BOR',
        })
        self.assertEqual(response.status_code,302)
        self.assertTrue(CartaTubo.objects.filter(numero_oficio='01-2026').exists())
        response=self.client.post(reverse('tubo:nueva_carta'),{
            'delegacion':self.d1.pk,'gestion':self.g2.pk,'asunto':'Vulneración','destinatario':'Vecina Uno',
            'estado':'BOR',
        })
        self.assertEqual(response.status_code,200)
        self.assertFalse(CartaTubo.objects.filter(asunto='Vulneración').exists())
