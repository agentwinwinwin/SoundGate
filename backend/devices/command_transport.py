import json
import threading
import uuid

import paho.mqtt.client as mqtt
from django.conf import settings

from .device_protocol import compact_json
from .onenet import OneNETError, generate_token


def down_topic(device):
    return settings.ONENET_CUSTOM_TOPIC_DOWN.format(
        pid=device.onenet_product_id, device=device.onenet_device_name,
    )


def publish_payload(device, payload):
    encoded = compact_json(payload)
    if not device.onenet_device_name:
        raise OneNETError('设备未配置 OneNET device_name。')
    connected = threading.Event()
    error = []
    client = mqtt.Client(
        mqtt.CallbackAPIVersion.VERSION2,
        client_id=f'soundgate-cmd-{uuid.uuid4().hex[:10]}', protocol=mqtt.MQTTv311,
    )
    client.username_pw_set(f'userid/{settings.ONENET_USER_ID}', generate_token(3600))

    def on_connect(client, userdata, flags, reason_code, properties):
        if reason_code == 0: connected.set()
        else: error.append(f'MQTT连接失败：{reason_code}'); connected.set()

    client.on_connect = on_connect
    try:
        client.connect(settings.ONENET_MQTT_HOST, settings.ONENET_MQTT_PORT, keepalive=60)
        client.loop_start()
        if not connected.wait(settings.ONENET_COMMAND_TIMEOUT_SECONDS):
            raise OneNETError('MQTT连接超时。')
        if error: raise OneNETError(error[0])
        info = client.publish(down_topic(device), encoded, qos=1)
        info.wait_for_publish(timeout=settings.ONENET_COMMAND_TIMEOUT_SECONDS)
        if not info.is_published(): raise OneNETError('MQTT发布超时。')
    finally:
        client.disconnect(); client.loop_stop()
    return {'topic': down_topic(device), 'frameBytes': len(encoded)}
