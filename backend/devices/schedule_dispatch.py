from django.utils import timezone

from .onenet import set_device_properties


def current_schedule_slot(device, now=None):
    """Return today's latest slot whose start time has already passed."""
    local_now = timezone.localtime(now or timezone.now())
    current_time = local_now.time().replace(tzinfo=None)
    return (
        device.schedule_slots
        .filter(weekday=local_now.isoweekday(), time__lte=current_time)
        .order_by('-time')
        .first()
    )


def dispatch_current_volume(device, now=None):
    """Send the volume that should currently be active for this device."""
    if not device.onenet_device_name:
        return None
    slot = current_schedule_slot(device, now)
    if slot is None:
        return None
    result = set_device_properties(device, {'DftVolume': slot.volume})
    return {
        'weekday': slot.weekday,
        'time': slot.time.strftime('%H:%M'),
        'volume': slot.volume,
        'transport': result['transport'],
    }
