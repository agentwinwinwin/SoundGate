import json
import uuid
import paho.mqtt.client as mqtt
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from devices.models import Device, FileTransfer, SignalInterfaceConfig, TerminalCommand
from devices.onenet import OneNETNotConfigured, generate_token

class Command(BaseCommand):
    help = '运行 OneNET 应用 MQTT 长连接，接收设备上下线和属性上报'

    def handle(self, *args, **options):
        try: password = generate_token(24 * 3600)
        except OneNETNotConfigured as exc: raise CommandError(str(exc))
        username = f'userid/{settings.ONENET_USER_ID}'
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f'soundgate-{uuid.uuid4().hex[:10]}', protocol=mqtt.MQTTv311)
        client.username_pw_set(username, password)

        def on_connect(client, userdata, flags, reason_code, properties):
            if reason_code != 0: raise CommandError(f'OneNET MQTT 连接失败：{reason_code}')
            product = settings.ONENET_PRODUCT_ID
            custom_up = settings.ONENET_CUSTOM_TOPIC_UP.format(pid=product)
            client.subscribe([(f'$sys/{product}/+/thing/lifecycle', 0), (f'$sys/{product}/+/thing/property', 0), (f'$sys/{product}/+/thing/property/set/reply', 0), (custom_up, 1)])
            self.stdout.write(self.style.SUCCESS(f'OneNET MQTT 已连接，监听产品 {product}'))

        def on_message(client, userdata, message):
            try: payload = json.loads(message.payload.decode())
            except Exception: return
            parts = message.topic.split('/')
            device_name = payload.get('deviceName')
            if not device_name:
                known_names = set(Device.objects.filter(onenet_product_id=settings.ONENET_PRODUCT_ID).values_list('onenet_device_name', flat=True))
                device_name = next((part for part in parts if part in known_names), parts[2] if len(parts) > 2 else None)
            device = Device.objects.filter(onenet_product_id=settings.ONENET_PRODUCT_ID, onenet_device_name=device_name).first()
            if not device: return
            if not message.topic.startswith('$sys/'):
                self.handle_custom(device, payload); return
            if message.topic.endswith('/lifecycle'):
                status = payload.get('data', {}).get('status')
                device.online = status == 'online'; device.cloud_connected = device.online; device.last_seen_at = timezone.now()
                device.save(update_fields=['online', 'cloud_connected', 'last_seen_at', 'updated_at']); return
            if message.topic.endswith('/thing/property'):
                params = payload.get('data', {}).get('params', {})
                values = {key: value.get('value') if isinstance(value, dict) else value for key, value in params.items()}
                device.last_telemetry = values; device.last_seen_at = timezone.now(); device.online = True; device.cloud_connected = True
                if 'DftEnable' in values: device.enabled = bool(values['DftEnable'])
                if 'DftVolume' in values: device.volume = max(0, min(9, int(values['DftVolume'])))
                device.save()

        client.on_connect = on_connect; client.on_message = on_message
        client.connect(settings.ONENET_MQTT_HOST, settings.ONENET_MQTT_PORT, keepalive=60)
        try: client.loop_forever(retry_first_connection=True)
        except KeyboardInterrupt: client.disconnect()

    def handle_custom(self, device, payload):
        message_type = payload.get('t')
        request_id = str(payload.get('id', ''))
        if message_type == 'fa':
            transfer = FileTransfer.objects.filter(device=device, transfer_id=request_id).first()
            if not transfer: return
            code = int(payload.get('code', 500))
            if code != 200:
                transfer.status = FileTransfer.Status.FAILED; transfer.error = str(payload.get('msg', '终端文件应答失败'))[:255]
            elif transfer.status == FileTransfer.Status.VERIFYING:
                transfer.status = FileTransfer.Status.SUCCEEDED; transfer.confirmed_at = timezone.now(); transfer.awaiting_chunk = None
                transfer.next_chunk = transfer.total_chunks
            else:
                number = int(payload.get('n', -1))
                if number == -1 and transfer.awaiting_chunk == -1:
                    transfer.awaiting_chunk = None
                elif number == transfer.awaiting_chunk:
                    transfer.next_chunk = max(transfer.next_chunk, number + 1); transfer.awaiting_chunk = None
                transfer.attempts = 0
            transfer.save(); return

        command = TerminalCommand.objects.filter(device=device, request_id=request_id).first()
        if message_type == 'ack' and command:
            code = int(payload.get('code', 500)); command.response = payload
            if code == 200:
                command.status = TerminalCommand.Status.SUCCEEDED; command.confirmed_at = timezone.now()
            elif code == 202: command.status = TerminalCommand.Status.PROCESSING
            else: command.status = TerminalCommand.Status.FAILED; command.error = str(payload.get('msg', '终端命令失败'))[:255]
            command.save(); return
        if message_type == 'bt_info':
            name = str(payload.get('name', ''))
            if name: device.bluetooth_name = name[:32]
            if command: command.status = TerminalCommand.Status.SUCCEEDED; command.response = payload; command.confirmed_at = timezone.now(); command.save()
            device.save(update_fields=['bluetooth_name', 'updated_at']); return
        if message_type == 'audio_info':
            manifest = dict(device.last_telemetry.get('audioManifest', {})); manifest[str(payload.get('k'))] = payload
            device.last_telemetry = {**device.last_telemetry, 'audioManifest': manifest}; device.save(update_fields=['last_telemetry', 'updated_at'])
            if command: command.status = TerminalCommand.Status.SUCCEEDED; command.response = payload; command.confirmed_at = timezone.now(); command.save()
            return
        if message_type == 'sig':
            device.last_telemetry = {**device.last_telemetry, 'signal': payload}; device.save(update_fields=['last_telemetry', 'updated_at'])
            config, _ = SignalInterfaceConfig.objects.get_or_create(device=device)
            config.confirmed = True; config.save(update_fields=['confirmed', 'updated_at'])
