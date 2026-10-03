import time

from django.core.management.base import BaseCommand
from django.utils import timezone

from devices.models import Device
from devices.onenet import OneNETError
from devices.schedule_dispatch import current_schedule_slot, dispatch_current_volume


class Command(BaseCommand):
    help = '按本地七天音量计划，将当前时段音量实时下发到 OneNET 设备'

    def handle(self, *args, **options):
        last_sent = {}
        self.stdout.write(self.style.SUCCESS('音量计划调度器已启动'))
        while True:
            now = timezone.now()
            for device in Device.objects.exclude(onenet_device_name=''):
                slot = current_schedule_slot(device, now)
                if slot is None:
                    continue
                signature = (slot.weekday, slot.time.isoformat(), slot.volume)
                if last_sent.get(device.device_id) == signature:
                    continue
                try:
                    dispatched = dispatch_current_volume(device, now)
                except OneNETError as exc:
                    self.stderr.write(f'{device.onenet_device_name}: {exc}')
                    continue
                if dispatched:
                    last_sent[device.device_id] = signature
                    self.stdout.write(
                        f'{device.onenet_device_name}: '
                        f'{dispatched["time"]} -> 音量 {dispatched["volume"]}'
                    )
            time.sleep(15)
