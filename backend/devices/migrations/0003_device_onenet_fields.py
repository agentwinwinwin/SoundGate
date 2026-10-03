from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [('devices', '0002_device_owner')]
    operations = [
        migrations.AddField(model_name='device', name='onenet_product_id', field=models.CharField(default='your-product-id', max_length=32, verbose_name='OneNET 产品 ID')),
        migrations.AddField(model_name='device', name='onenet_device_name', field=models.CharField(blank=True, max_length=64, verbose_name='OneNET 设备名称')),
        migrations.AddField(model_name='device', name='last_telemetry', field=models.JSONField(blank=True, default=dict, verbose_name='最近上报参数')),
    ]
