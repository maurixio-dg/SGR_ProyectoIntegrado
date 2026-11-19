from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):
    dependencies = [
        ('catalogos', '0002_funcion'),
        ('matriz_sgr', '0002_medicionespecialsgr_auditoriamedicionespecialsgr_and_more'),
    ]
    operations = [
        migrations.CreateModel(
            name='CorrespondenciaHojaCargoSGR',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('hoja', models.CharField(max_length=50)),
                ('actualizado_en', models.DateTimeField(auto_now=True)),
                ('cargo', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='hojas_matriz_sgr', to='catalogos.cargo')),
                ('catalogo', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='correspondencias_cargo', to='matriz_sgr.catalogomatrizsgr')),
            ],
            options={'verbose_name':'Correspondencia hoja/cargo de la matriz'},
        ),
        migrations.AddConstraint(
            model_name='correspondenciahojacargosgr',
            constraint=models.UniqueConstraint(fields=('catalogo','hoja'), name='uq_hoja_cargo_matriz_sgr'),
        ),
    ]
