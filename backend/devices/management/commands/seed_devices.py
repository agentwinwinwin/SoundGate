from datetime import time
import os
from django.core.management.base import BaseCommand
from devices.models import AudioConfig, Device, ScheduleSlot
from django.contrib.auth import get_user_model

DEVICES = [
    ('SG000001', 'Demo Crossing A', 'SoundGate-A', '示例街道A', 7, 'device-a'),
    ('SG000002', 'Demo Crossing B', 'SoundGate-B', '示例街道B', 0, 'device-b'),
    ('SG000003', 'Local Demo Device', 'SoundGate-C', '示例街道C', 5, ''),
]
SLOTS = [(time(7), 7), (time(8), 9), (time(15), 5), (time(17), 7), (time(20), 5), (time(23), 2)]

class Command(BaseCommand):
    help = '写入 SoundGate 演示设备和每周计划'

    def add_arguments(self, parser):
        parser.add_argument('--username', default=os.getenv('SOUNDGATE_SEED_USERNAME', 'admin'))
        parser.add_argument('--password', default=os.getenv('SOUNDGATE_SEED_PASSWORD', ''))

    def handle(self, *args, **options):
        password = options['password']
        if len(password) < 8:
            self.stderr.write(self.style.ERROR(
                '请通过 --password 或 SOUNDGATE_SEED_PASSWORD 提供至少 8 位的演示管理员密码。'
            ))
            return
        User = get_user_model()
        admin, _ = User.objects.get_or_create(
            username=options['username'], defaults={'is_staff': True, 'is_superuser': True}
        )
        admin.is_staff = True; admin.is_superuser = True; admin.set_password(password); admin.save()
        for index, (device_id, name, bluetooth, street, volume, onenet_name) in enumerate(DEVICES):
            device, _ = Device.objects.update_or_create(device_id=device_id, defaults={'owner': admin, 'name': name, 'bluetooth_name': bluetooth, 'volume': volume, 'onenet_device_name': onenet_name, 'online': index != 1, 'enabled': index != 1, 'cloud_connected': index != 1, 'gps_status': 'normal' if index != 1 else 'no_signal'})
            AudioConfig.objects.update_or_create(device=device, defaults={'street_name': street})
            if not device.schedule_slots.exists():
                ScheduleSlot.objects.bulk_create([ScheduleSlot(device=device, weekday=day, time=slot_time, volume=slot_volume) for day in range(1, 8) for slot_time, slot_volume in SLOTS])
        self.stdout.write(self.style.SUCCESS('演示设备已写入。'))
