from types import SimpleNamespace
from unittest.mock import patch
from pathlib import Path
from io import BytesIO
import json
import re
import wave

from django.test import SimpleTestCase, override_settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from .onenet import MAX_FRAME_BYTES, OneNETError, _set_modern_properties, build_device_frame, get_device_parameters, set_device_properties
from .device_protocol import compact_json, prepare_file_transfer, protocol_manifest, validate_wav_bytes
from .models import AudioConfig, Device


class OneNETProtocolTests(SimpleTestCase):
    def setUp(self):
        self.device = SimpleNamespace(
            onenet_product_id='p1',
            onenet_device_name='d1',
        )

    def test_documented_frame_is_compact_and_within_limit(self):
        params = {
            'DftEdMinute': 59, 'DftEnable': 1, 'DftStHour': 0,
            'DftStMinute': 0, 'DftVolume': 2, 'DtfEdHour': 23,
            'Period': 60, 'RushTime': 8, 'WalkTime': 15,
        }
        frame, encoded = build_device_frame(self.device, params)
        self.assertEqual(frame['device_name'], 'd1')
        self.assertLessEqual(len(encoded), MAX_FRAME_BYTES)
        self.assertNotIn(b' ', encoded)

    def test_unknown_parameter_is_rejected(self):
        with self.assertRaises(OneNETError):
            build_device_frame(self.device, {'Unknown': 1})

    def test_property_types_and_ranges_match_manifest(self):
        for params in ({'DftVolume': 10}, {'Period': 3601}, {'DftEnable': '1'}, {'State': 1}):
            with self.subTest(params=params), self.assertRaises(OneNETError):
                build_device_frame(self.device, params)
        _, encoded = build_device_frame(self.device, {'DftVolume': 9, 'Period': 3600})
        self.assertLessEqual(len(encoded), MAX_FRAME_BYTES)

    def test_manifest_marks_unconnected_capabilities_truthfully(self):
        manifest = protocol_manifest()
        self.assertEqual(manifest['bluetooth']['status'], 'pending_terminal_protocol')
        self.assertEqual(manifest['streetAudio']['status'], 'local_only')
        self.assertEqual(manifest['audio']['status'], 'server_validation_ready')
        self.assertEqual(manifest['fileTransfer']['transportStatus'], 'pending_joint_test')
        self.assertEqual(manifest['signalController']['status'], 'requirements_pending')
        self.assertEqual(manifest['bluetooth']['maxNameBytes'], 32)

    def test_documented_mqtt_json_samples_are_valid_and_within_limit(self):
        document = (Path(__file__).resolve().parents[2] / 'docs' / 'SoundGate终端平台MQTT通信协议.md').read_text()
        mqtt_text = document.split('## 14 SoundGate后端HTTP接口')[0]
        mqtt_text += document.split('## 15 终端MQTT扩展接口')[1].split('## 16 双方开发任务清单')[0]
        samples = re.findall(r'```json\n([^\n]+)\n```', mqtt_text)
        self.assertGreater(len(samples), 0)
        for sample in samples:
            with self.subTest(sample=sample):
                payload = json.loads(sample)
                self.assertLessEqual(len(compact_json(payload)), MAX_FRAME_BYTES)

    def test_file_chunk_envelope_stays_below_200_bytes(self):
        transfer = prepare_file_transfer('walk', 'walk.wav', 4096, '1234abcd')
        self.assertLessEqual(transfer['worstCaseChunkFrameBytes'], 200)
        self.assertLessEqual(len(compact_json(transfer['beginFrame'])), 200)

    def test_wav_validation_accepts_terminal_format(self):
        output = BytesIO()
        with wave.open(output, 'wb') as wav:
            wav.setnchannels(1); wav.setsampwidth(1); wav.setframerate(8000)
            wav.writeframes(bytes([128]) * 16000)
        result = validate_wav_bytes('rush', output.getvalue())
        self.assertEqual(result['duration'], 2.0)
        self.assertEqual(result['sampleRate'], 8000)
        self.assertRegex(result['crc32'], r'^[0-9a-f]{8}$')

    @override_settings(ONENET_AUTH_MODE='api_key', ONENET_API_KEY='test-key')
    @patch('devices.onenet._send_legacy_command')
    def test_api_key_mode_sends_exact_custom_frame(self, send):
        send.return_value = {'errno': 0, 'data': {'cmd_uuid': 'test'}}
        result = set_device_properties(self.device, {'DftEnable': 1})
        self.assertEqual(result['transport'], 'legacy_command')
        self.assertIn(b'"device_name":"d1"', send.call_args.args[0])

    @override_settings(ONENET_AUTH_MODE='device_key', ONENET_DEVICE_TOKEN='test-token')
    @patch('devices.onenet._set_modern_properties')
    def test_device_key_mode_sets_real_property(self, send):
        send.return_value = {'code': 0}
        result = set_device_properties(self.device, {'DftVolume': 2})
        self.assertEqual(result['transport'], 'device_property')

    @override_settings(
        ONENET_API_URL='https://example.test/property',
        ONENET_DEVICE_TOKEN='test-token',
        ONENET_USER_ID='',
    )
    @patch('devices.onenet._json_request')
    def test_real_property_request_contains_target_and_params(self, request):
        request.return_value = {'code': 0, 'msg': 'succ'}
        _set_modern_properties(self.device, {'DftEnable': 1, 'DftVolume': 6})
        args, kwargs = request.call_args
        self.assertEqual(args[0], 'https://example.test/property')
        self.assertIn(b'"device_name":"d1"', kwargs['body'])
        self.assertIn(b'"DftVolume":6', kwargs['body'])

    @override_settings(ONENET_USER_ID='', ONENET_DEVICE_TOKEN='test-token')
    @patch('devices.onenet._get_live_property_values')
    @patch('devices.onenet._json_request')
    def test_parameter_query_returns_only_reported_real_values(self, request, live_values):
        live_values.return_value = {'DftVolume': '4', 'DftEnable': None}
        request.return_value = {
            'code': 0,
            'data': [
                {'identifier': 'DftVolume', 'value': '4', 'expect_value': '6', 'name': '喇叭音量', 'data_type': 'int32'},
                {'identifier': 'DftEnable', 'expect_value': '1', 'name': '参数设置使能', 'data_type': 'int32'},
            ],
        }
        result = get_device_parameters('d1')
        self.assertEqual(result['DftVolume']['value'], '4')
        self.assertEqual(result['DftVolume']['displayValue'], '4')
        self.assertIsNone(result['DftEnable']['value'])
        self.assertIsNone(result['DftEnable']['displayValue'])

    def test_long_identifiers_cannot_bypass_frame_limit(self):
        device = SimpleNamespace(onenet_product_id='p' * 32, onenet_device_name='d' * 64)
        with self.assertRaises(OneNETError):
            build_device_frame(device, {
                'DftEdMinute': 59, 'DftEnable': 1, 'DftStHour': 0,
                'DftStMinute': 0, 'DftVolume': 9, 'DtfEdHour': 23,
                'Period': 3600, 'RushTime': 3600, 'WalkTime': 3600,
            })


@override_settings(ONENET_PRODUCT_ID='test-product')
class DeviceDeliveryFlowTests(APITestCase):
    """Simulate one device from cloud discovery through terminal confirmation."""

    def setUp(self):
        self.user = get_user_model().objects.create_user('flow-user', password='123456')

    @patch('devices.views.get_device_snapshot')
    @patch('devices.views.list_product_devices')
    @patch('devices.views.set_device_properties')
    @patch('devices.views.dispatch_current_volume')
    def test_complete_device_delivery_flow(self, dispatch, set_properties, list_devices, snapshot):
        list_devices.return_value = ([{'device_name': 'sim-device', 'status': 1}], 1)
        snapshot.return_value = {
            'deviceName': 'sim-device', 'online': True,
            'params': {'DftEnable': 0, 'DftVolume': 2}, 'latestTime': 1789092000000,
        }
        set_properties.return_value = {'transport': 'device_property'}
        dispatch.return_value = {'weekday': 5, 'time': '08:00', 'volume': 6, 'transport': 'device_property'}

        login = self.client.post('/api/auth/login/', {'username': 'flow-user', 'password': '123456'}, format='json')
        self.assertEqual(login.status_code, 200)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {login.data["token"]}')

        available = self.client.get('/api/devices/onenet/available/')
        self.assertEqual(available.status_code, 200)
        self.assertEqual(available.data['devices'][0]['deviceName'], 'sim-device')

        imported = self.client.post('/api/devices/onenet/import/', {'deviceNames': ['sim-device']}, format='json')
        self.assertEqual(imported.status_code, 201)
        device_id = imported.data[0]['id']
        self.assertEqual(imported.data[0]['volume'], 2)
        self.assertFalse(imported.data[0]['enabled'])

        desired = self.client.post(
            f'/api/devices/{device_id}/onenet/parameters/',
            {'DftEnable': 1, 'DftVolume': 6}, format='json',
        )
        self.assertEqual(desired.status_code, 200)
        set_properties.assert_called_once()

        schedule = self.client.put(
            f'/api/devices/{device_id}/schedule/',
            {'slots': [{'weekday': 5, 'time': '08:00', 'volume': 6}]}, format='json',
        )
        self.assertEqual(schedule.status_code, 200)
        self.assertEqual(schedule.data['currentDispatch']['volume'], 6)

        # The terminal reports the desired values later; only then does local
        # actual state change to ON / volume 6.
        snapshot.return_value = {
            'deviceName': 'sim-device', 'online': True,
            'params': {'DftEnable': 1, 'DftVolume': 6}, 'latestTime': 1789092060000,
        }
        synced = self.client.post('/api/devices/onenet/sync/', {}, format='json')
        self.assertEqual(synced.status_code, 200)
        device = self.client.get(f'/api/devices/{device_id}/')
        self.assertEqual(device.status_code, 200)
        self.assertTrue(device.data['enabled'])
        self.assertEqual(device.data['volume'], 6)
        self.assertIsNotNone(device.data['lastSeen'])

        other = get_user_model().objects.create_user('other-user', password='123456')
        self.client.force_authenticate(other)
        self.assertEqual(self.client.get(f'/api/devices/{device_id}/').status_code, 404)


class PendingTerminalContractTests(APITestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('contract-user', password='123456')
        self.client.force_authenticate(self.user)
        self.device = Device.objects.create(
            device_id='SG000001', owner=self.user, name='Demo Device',
            onenet_product_id='test-product', onenet_device_name='device-b',
            bluetooth_name='SoundGate-Demo',
        )
        AudioConfig.objects.create(device=self.device)

    def test_street_name_response_does_not_claim_terminal_success(self):
        response = self.client.patch(
            '/api/devices/SG000001/audio-config/', {'streetName': '中山路'}, format='json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['delivery'], 'local_only')
        self.assertFalse(response.data['terminalConfirmed'])

    @override_settings(DEVICE_ADMIN_PASSWORD='test-password')
    def test_bluetooth_response_does_not_claim_terminal_success(self):
        response = self.client.post(
            '/api/devices/SG000001/rename-bluetooth/',
            {'bluetoothName': 'SoundGate-Demo-2', 'password': 'test-password'}, format='json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['delivery'], 'pending_terminal_protocol')
        self.assertFalse(response.data['terminalConfirmed'])
        self.assertNotIn('password', response.data)

    @override_settings(DEVICE_ADMIN_PASSWORD='test-password')
    def test_bluetooth_name_limit_is_utf8_bytes_not_characters(self):
        response = self.client.post(
            '/api/devices/SG000001/rename-bluetooth/',
            {'bluetoothName': '蓝' * 11, 'password': 'test-password'}, format='json',
        )
        self.assertEqual(response.status_code, 400)

    def test_protocol_endpoint_exposes_pending_capabilities(self):
        response = self.client.get('/api/devices/SG000001/protocol/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['fileTransfer']['status'], 'preflight_ready')
        self.assertEqual(response.data['bluetooth']['status'], 'pending_terminal_protocol')

    def test_audio_upload_is_server_validated_but_not_terminal_confirmed(self):
        output = BytesIO()
        with wave.open(output, 'wb') as wav:
            wav.setnchannels(1); wav.setsampwidth(1); wav.setframerate(8000)
            wav.writeframes(bytes([128]) * 16000)
        uploaded = SimpleUploadedFile('rush.wav', output.getvalue(), content_type='audio/wav')
        response = self.client.post(
            '/api/devices/SG000001/audio-files/',
            {'kind': 'rush', 'file': uploaded}, format='multipart',
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['file']['duration'], 2.0)
        self.assertEqual(response.data['delivery'], 'server_validated')
        self.assertFalse(response.data['terminalConfirmed'])
        self.assertFalse(response.data['transferPlan']['transportReady'])
