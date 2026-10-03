import json
import uuid
import paho.mqtt.client as mqtt
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from devices.models import Device
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
            client.subscribe([(f'$sys/{product}/+/thing/lifecycle', 0), (f'$sys/{product}/+/thing/property', 0), (f'$sys/{product}/+/thing/property/set/reply', 0)])
            self.stdout.write(self.style.SUCCESS(f'OneNET MQTT 已连接，监听产品 {product}'))

        def on_message(client, userdata, message):
            try: payload = json.loads(message.payload.decode())
            except Exception: return
            parts = message.topic.split('/'); device_name = parts[2] if len(parts) > 2 else payload.get('deviceName')
            device = Device.objects.filter(onenet_product_id=settings.ONENET_PRODUCT_ID, onenet_device_name=device_name).first()
            if not device: return
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
