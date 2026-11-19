from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('tubo', '0001_initial'),
        ('gestion', '0004_ausenciasgr_configuracionmetasgr'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]
    operations = [
        migrations.CreateModel(
            name='VinculoGestionActividad',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('vinculado_en', models.DateTimeField(auto_now_add=True)),
                ('actividad', models.OneToOneField(on_delete=django.db.models.deletion.PROTECT,
                     related_name='origen_tubo', to='gestion.actividad')),
                ('gestion', models.OneToOneField(on_delete=django.db.models.deletion.PROTECT,
                     related_name='vinculo_actividad', to='tubo.gestionsocial')),
                ('vinculado_por', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,
                     related_name='vinculaciones_tubo', to=settings.AUTH_USER_MODEL)),
            ],
            options={'verbose_name': 'Vínculo de gestión social con actividad',
                     'verbose_name_plural': 'Vínculos de gestiones sociales con actividades'},
        ),
    ]
