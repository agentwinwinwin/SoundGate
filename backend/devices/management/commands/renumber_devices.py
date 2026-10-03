from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from devices.models import AudioConfig, Device, ScheduleSlot


class Command(BaseCommand):
    help = '按当前设备编号顺序从 SG000001 开始重新编号'

    @transaction.atomic
    def handle(self, *args, **options):
        devices = list(Device.objects.select_related('owner').order_by('device_id'))
        targets = [f'SG{index:06d}' for index in range(1, len(devices) + 1)]
        occupied = set(Device.objects.filter(device_id__in=targets).values_list('device_id', flat=True))
        conflicts = {target for device, target in zip(devices, targets) if target in occupied and device.device_id != target}
        if conflicts:
            raise CommandError(f'目标编号已被占用：{", ".join(sorted(conflicts))}')

        for device, target in zip(devices, targets):
            if device.device_id == target:
                continue
            old_id = device.device_id
            new_device = Device.objects.create(
                device_id=target, owner=device.owner,
                onenet_product_id=device.onenet_product_id,
                onenet_device_name=device.onenet_device_name,
                name=device.name, online=device.online, enabled=device.enabled,
                volume=device.volume, last_seen_at=device.last_seen_at,
                gps_status=device.gps_status, cloud_connected=device.cloud_connected,
                bluetooth_name=device.bluetooth_name, last_telemetry=device.last_telemetry,
            )
            ScheduleSlot.objects.filter(device=device).update(device=new_device)
            AudioConfig.objects.filter(device=device).update(device=new_device)
            device.delete()
            self.stdout.write(f'{old_id} -> {target}')
        self.stdout.write(self.style.SUCCESS('设备编号重排完成。'))
