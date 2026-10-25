import django.db.models.deletion
import devices.models
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('devices', '0004_audioconfig_file_metadata')]

    operations = [
        migrations.CreateModel(
            name='DeviceAudioFile',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('kind', models.CharField(choices=[('walk', '慢行提示音'), ('rush', '快行提示音'), ('custom', '自定义音频')], max_length=16)),
                ('file', models.FileField(upload_to='audio/%Y/%m/%d')),
                ('original_name', models.CharField(max_length=255)), ('size', models.PositiveIntegerField()),
                ('duration_ms', models.PositiveIntegerField()), ('crc32', models.CharField(max_length=8)),
                ('metadata', models.JSONField(blank=True, default=dict)), ('created_at', models.DateTimeField(auto_now_add=True)),
                ('device', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='audio_files', to='devices.device')),
            ],
        ),
        migrations.CreateModel(
            name='TerminalCommand',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('request_id', models.CharField(max_length=16, unique=True)), ('command_type', models.CharField(max_length=32)),
                ('payload', models.JSONField(default=dict)),
                ('status', models.CharField(choices=[('queued','排队中'),('sent','已发送'),('processing','终端处理中'),('succeeded','已确认'),('failed','失败'),('cancelled','已取消')], default='queued', max_length=16)),
                ('attempts', models.PositiveSmallIntegerField(default=0)), ('response', models.JSONField(blank=True, default=dict)),
                ('error', models.CharField(blank=True, max_length=255)), ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)), ('confirmed_at', models.DateTimeField(blank=True, null=True)),
                ('device', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='terminal_commands', to='devices.device')),
            ],
        ),
        migrations.CreateModel(
            name='FileTransfer',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('transfer_id', models.CharField(max_length=16, unique=True)),
                ('status', models.CharField(choices=[('queued','排队中'),('transferring','传输中'),('verifying','终端校验中'),('succeeded','已完成'),('failed','失败'),('cancelled','已取消')], default='queued', max_length=16)),
                ('next_chunk', models.PositiveIntegerField(default=0)), ('awaiting_chunk', models.IntegerField(blank=True, null=True)), ('total_chunks', models.PositiveIntegerField()),
                ('attempts', models.PositiveSmallIntegerField(default=0)), ('error', models.CharField(blank=True, max_length=255)),
                ('created_at', models.DateTimeField(auto_now_add=True)), ('updated_at', models.DateTimeField(auto_now=True)),
                ('confirmed_at', models.DateTimeField(blank=True, null=True)),
                ('audio_file', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='transfers', to='devices.deviceaudiofile')),
                ('device', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='file_transfers', to='devices.device')),
            ],
        ),
        migrations.CreateModel(
            name='SignalInterfaceConfig',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('mode', models.CharField(choices=[('io','数字输入'),('rs485','RS-485')], default='io', max_length=8)),
                ('io_inputs', models.JSONField(default=devices.models.default_signal_inputs)), ('rs485', models.JSONField(blank=True, default=dict)),
                ('confirmed', models.BooleanField(default=False)), ('updated_at', models.DateTimeField(auto_now=True)),
                ('device', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='signal_interface', to='devices.device')),
            ],
        ),
    ]
