from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('devices', '0003_device_onenet_fields')]

    operations = [
        migrations.AddField(
            model_name='audioconfig',
            name='file_metadata',
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
