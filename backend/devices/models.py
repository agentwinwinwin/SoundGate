from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.conf import settings

class Device(models.Model):
    class GPSStatus(models.TextChoices):
        NORMAL = 'normal', '正常'
        ERROR = 'error', '异常'
        NO_SIGNAL = 'no_signal', '无信号'

    device_id = models.CharField('设备编号', max_length=64, primary_key=True)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='devices', on_delete=models.CASCADE, null=True, blank=True, verbose_name='所属账号')
    onenet_product_id = models.CharField(max_length=32, default='your-product-id', verbose_name='OneNET 产品 ID')
    onenet_device_name = models.CharField(max_length=64, blank=True, verbose_name='OneNET 设备名称')
    name = models.CharField('设备名称', max_length=128)
    online = models.BooleanField('在线', default=False)
    enabled = models.BooleanField('开启', default=False)
    volume = models.PositiveSmallIntegerField('当前音量', default=0, validators=[MinValueValidator(0), MaxValueValidator(9)])
    last_seen_at = models.DateTimeField('最后通信时间', null=True, blank=True)
    gps_status = models.CharField('GPS 状态', max_length=16, choices=GPSStatus.choices, default=GPSStatus.NO_SIGNAL)
    cloud_connected = models.BooleanField('云端连接', default=False)
    bluetooth_name = models.CharField('蓝牙名称', max_length=32)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_telemetry = models.JSONField(default=dict, blank=True, verbose_name='最近上报参数')

    class Meta:
        ordering = ['device_id']

    def __str__(self):
        return f'{self.name} ({self.device_id})'

class ScheduleSlot(models.Model):
    class Weekday(models.IntegerChoices):
        MONDAY = 1, '周一'; TUESDAY = 2, '周二'; WEDNESDAY = 3, '周三'; THURSDAY = 4, '周四'
        FRIDAY = 5, '周五'; SATURDAY = 6, '周六'; SUNDAY = 7, '周日'

    device = models.ForeignKey(Device, related_name='schedule_slots', on_delete=models.CASCADE)
    weekday = models.PositiveSmallIntegerField(choices=Weekday.choices)
    time = models.TimeField()
    volume = models.PositiveSmallIntegerField(validators=[MinValueValidator(0), MaxValueValidator(9)])

    class Meta:
        ordering = ['weekday', 'time']
        constraints = [models.UniqueConstraint(fields=['device', 'weekday', 'time'], name='unique_device_weekday_time')]

class AudioConfig(models.Model):
    device = models.OneToOneField(Device, related_name='audio_config', on_delete=models.CASCADE)
    street_name = models.CharField('街道名称', max_length=200, blank=True)
    walk_file_name = models.CharField(max_length=255, blank=True)
    rush_file_name = models.CharField(max_length=255, blank=True)
    custom_file_name = models.CharField(max_length=255, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
