from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("usuarios", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="usuario",
            name="debe_cambiar_password",
            field=models.BooleanField(default=False, verbose_name="Cambio de contraseña pendiente"),
        ),
    ]
