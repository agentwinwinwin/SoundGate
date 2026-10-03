import time

from django.core.management.base import BaseCommand, CommandError

from devices.models import Device
from devices.onenet import ALLOWED_PARAMS, OneNETError, _get_live_property_values, set_device_properties


PARAM_ORDER = [
    'DftEnable', 'DftVolume', 'DftStHour', 'DftStMinute',
    'DtfEdHour', 'DftEdMinute', 'Period', 'RushTime', 'WalkTime',
]


def adjacent_value(name, value):
    value = int(value)
    if name == 'DftEnable':
        return 0 if value else 1
    limits = {
        'DftVolume': 9,
        'DftStHour': 23,
        'DftStMinute': 59,
        'DtfEdHour': 23,
        'DftEdMinute': 59,
    }
    maximum = limits.get(name)
    if maximum is not None:
        return value - 1 if value >= maximum else value + 1
    return value + 1


class Command(BaseCommand):
    help = '逐项测试 OneNET 可写属性，并在每项测试后恢复终端原值'

    def add_arguments(self, parser):
        parser.add_argument('--device', required=True, help='OneNET device_name')

    def read_value(self, device_name, name):
        return _get_live_property_values(device_name, [name]).get(name)

    def wait_value(self, device_name, name, expected, attempts=5):
        last = None
        for _ in range(attempts):
            time.sleep(2)
            last = self.read_value(device_name, name)
            if last is not None and int(last) == int(expected):
                return True, last
        return False, last

    def handle(self, *args, **options):
        device_name = options['device']
        try:
            device = Device.objects.get(onenet_device_name=device_name)
        except Device.DoesNotExist as exc:
            raise CommandError(f'本地未找到 OneNET 设备 {device_name}') from exc

        unknown = set(PARAM_ORDER) - ALLOWED_PARAMS
        if unknown:
            raise CommandError(f'协议字段未注册：{sorted(unknown)}')

        results = []
        for name in PARAM_ORDER:
            original = None
            test_value = None
            changed = False
            restored = False
            detail = ''
            try:
                original = self.read_value(device_name, name)
                if original is None:
                    raise OneNETError('终端未返回原值')
                test_value = adjacent_value(name, original)
                response = set_device_properties(device, {name: test_value})
                ack = response['response'].get('data') or {}
                if int(ack.get('code', 0)) != 200:
                    raise OneNETError(f'终端应答异常：{ack}')
                changed, actual = self.wait_value(device_name, name, test_value)
                if not changed:
                    detail = f'测试值未确认，最后读取 {actual}'
            except Exception as exc:
                detail = str(exc)
            finally:
                if original is not None:
                    try:
                        set_device_properties(device, {name: int(original)})
                        restored, restored_value = self.wait_value(device_name, name, original)
                        if not restored:
                            detail = f'{detail}; 恢复未确认，最后读取 {restored_value}'.strip('; ')
                    except Exception as exc:
                        detail = f'{detail}; 恢复失败：{exc}'.strip('; ')

            passed = changed and restored
            results.append(passed)
            state = self.style.SUCCESS('PASS') if passed else self.style.ERROR('FAIL')
            self.stdout.write(
                f'{state} {name}: {original} -> {test_value} -> {original}'
                + (f'；{detail}' if detail else '')
            )

        passed_count = sum(results)
        self.stdout.write(f'结果：{passed_count}/{len(results)} 项通过并恢复原值')
        if passed_count != len(results):
            raise CommandError('存在未通过或未确认恢复的属性，请检查上述结果。')
