from rest_framework import status, viewsets
from rest_framework.authtoken.models import Token
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from django.contrib.auth import authenticate, get_user_model
from django.conf import settings
from datetime import datetime, timezone as datetime_timezone
from .models import AudioConfig, Device
from .serializers import AudioConfigSerializer, BluetoothRenameSerializer, DeviceCreateSerializer, DeviceSerializer, OneNETImportSerializer, OneNETParametersSerializer, ScheduleSlotSerializer, WeeklyScheduleSerializer
from .onenet import OneNETError, OneNETNotConfigured, get_device_parameters, get_device_snapshot, list_product_devices, set_device_properties
from .schedule_dispatch import dispatch_current_volume
from .device_protocol import prepare_file_transfer, protocol_manifest


def apply_onenet_snapshot(device, snapshot):
    params = snapshot['params']
    device.online = snapshot['online']
    device.cloud_connected = snapshot['online']
    if 'DftEnable' in params:
        device.enabled = bool(int(params['DftEnable']))
    if 'DftVolume' in params:
        volume = int(params['DftVolume'])
        if 0 <= volume <= 9:
            device.volume = volume
    latest_time = snapshot.get('latestTime')
    if latest_time is not None:
        timestamp = float(latest_time)
        # OneNET commonly returns milliseconds; accept seconds as well.
        if timestamp > 10_000_000_000:
            timestamp /= 1000
        device.last_seen_at = datetime.fromtimestamp(timestamp, tz=datetime_timezone.utc)
    device.last_telemetry = {**device.last_telemetry, **params}
    device.save(update_fields=['online', 'cloud_connected', 'enabled', 'volume', 'last_seen_at', 'last_telemetry', 'updated_at'])
    return device


def next_device_id():
    numbers = []
    for value in Device.objects.values_list('device_id', flat=True):
        if value.startswith('SG') and len(value) == 8 and value[2:].isdigit():
            numbers.append(int(value[2:]))
    number = max(numbers, default=0) + 1
    if number > 999999:
        raise ValueError('设备编号已超过 SG999999。')
    return f'SG{number:06d}'

class DeviceViewSet(viewsets.ModelViewSet):
    queryset = Device.objects.all()
    serializer_class = DeviceSerializer
    lookup_field = 'device_id'
    http_method_names = ['get', 'post', 'put', 'patch', 'delete', 'head', 'options']

    def get_queryset(self):
        return Device.objects.filter(owner=self.request.user)

    def get_serializer_class(self):
        return DeviceCreateSerializer if self.action == 'create' else DeviceSerializer

    def partial_update(self, request, *args, **kwargs):
        device = self.get_object()
        serializer = self.get_serializer(device, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        params = {}
        if 'enabled' in serializer.validated_data: params['DftEnable'] = int(serializer.validated_data['enabled'])
        if 'volume' in serializer.validated_data: params['DftVolume'] = serializer.validated_data['volume']
        if params:
            try: set_device_properties(device, params)
            except OneNETNotConfigured as exc: return Response({'detail': str(exc), 'code': 'onenet_not_configured'}, status=503)
            except OneNETError as exc: return Response({'detail': str(exc), 'code': 'onenet_error'}, status=502)
        # Keep local status unchanged until the terminal reports the applied value.
        serializer.save(enabled=device.enabled, volume=device.volume)
        return Response(serializer.data)

    @action(detail=False, methods=['get'], url_path='onenet/available')
    def onenet_available(self, request):
        try:
            cloud_devices, total = list_product_devices()
        except OneNETNotConfigured as exc:
            return Response({'detail': str(exc), 'code': 'onenet_not_configured'}, status=503)
        except OneNETError as exc:
            return Response({'detail': str(exc), 'code': 'onenet_error'}, status=502)
        names = [str(item.get('device_name') or item.get('name') or '') for item in cloud_devices]
        existing = {
            device.onenet_device_name: device
            for device in Device.objects.filter(onenet_product_id=settings.ONENET_PRODUCT_ID, onenet_device_name__in=names)
        }
        rows = []
        for item, name in zip(cloud_devices, names):
            if not name:
                continue
            local = existing.get(name)
            raw_status = item.get('status')
            rows.append({
                'deviceName': name,
                'online': raw_status in (1, '1', 'online'),
                'added': bool(local and local.owner_id == request.user.id),
                'claimed': bool(local and local.owner_id != request.user.id),
            })
        return Response({'devices': rows, 'total': total})

    @action(detail=False, methods=['post'], url_path='onenet/import')
    def onenet_import(self, request):
        serializer = OneNETImportSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            cloud_devices, _ = list_product_devices()
        except OneNETNotConfigured as exc:
            return Response({'detail': str(exc), 'code': 'onenet_not_configured'}, status=503)
        except OneNETError as exc:
            return Response({'detail': str(exc), 'code': 'onenet_error'}, status=502)
        by_name = {
            str(item.get('device_name') or item.get('name')): item
            for item in cloud_devices
        }
        requested = serializer.validated_data['deviceNames']
        missing = [name for name in requested if name not in by_name]
        if missing:
            return Response({'detail': f'OneNET 中不存在设备：{", ".join(missing)}'}, status=400)
        imported = []
        for name in requested:
            existing = Device.objects.filter(
                onenet_product_id=settings.ONENET_PRODUCT_ID,
                onenet_device_name=name,
            ).first()
            if existing:
                if existing.owner_id != request.user.id:
                    return Response({'detail': f'设备 {name} 已属于其他账号。'}, status=409)
                continue
            cloud = by_name[name]
            raw_status = cloud.get('status')
            device_id = next_device_id()
            device = Device.objects.create(
                device_id=device_id,
                owner=request.user,
                onenet_product_id=settings.ONENET_PRODUCT_ID,
                onenet_device_name=name,
                name=name,
                bluetooth_name=f'SoundGate-{name}'[:32],
                online=raw_status in (1, '1', 'online'),
                cloud_connected=raw_status in (1, '1', 'online'),
            )
            AudioConfig.objects.create(device=device)
            try:
                apply_onenet_snapshot(device, get_device_snapshot(name))
            except OneNETError:
                # Import succeeds even if OneNET becomes temporarily unavailable.
                pass
            imported.append(device)
        return Response(DeviceSerializer(imported, many=True).data, status=201)

    @action(detail=False, methods=['post'], url_path='onenet/sync')
    def onenet_sync(self, request):
        synced = []
        errors = []
        for device in self.get_queryset().exclude(onenet_device_name=''):
            try:
                snapshot = get_device_snapshot(device.onenet_device_name)
                apply_onenet_snapshot(device, snapshot)
                synced.append({
                    'deviceName': device.onenet_device_name,
                    'params': snapshot['params'],
                    'online': snapshot['online'],
                })
            except (OneNETError, ValueError, TypeError) as exc:
                errors.append({'deviceName': device.onenet_device_name, 'detail': str(exc)})
        return Response({'synced': synced, 'errors': errors})

    @action(detail=True, methods=['get', 'post'], url_path='onenet/parameters')
    def onenet_parameters(self, request, device_id=None):
        device = self.get_object()
        if request.method == 'GET':
            identifiers = [value for value in request.query_params.get('keys', '').split(',') if value] or None
            try:
                parameters = get_device_parameters(device.onenet_device_name, identifiers)
            except OneNETNotConfigured as exc:
                return Response({'detail': str(exc), 'code': 'onenet_not_configured'}, status=503)
            except OneNETError as exc:
                return Response({'detail': str(exc), 'code': 'onenet_error'}, status=502)
            return Response({'parameters': parameters})
        serializer = OneNETParametersSerializer(data=request.data); serializer.is_valid(raise_exception=True)
        try: result = set_device_properties(device, serializer.validated_data)
        except OneNETNotConfigured as exc: return Response({'detail': str(exc), 'code': 'onenet_not_configured'}, status=503)
        except OneNETError as exc: return Response({'detail': str(exc), 'code': 'onenet_error'}, status=502)
        return Response(result)

    @action(detail=True, methods=['get', 'put'], url_path='schedule')
    def schedule(self, request, device_id=None):
        device = self.get_object()
        if request.method == 'GET':
            return Response({'slots': ScheduleSlotSerializer(device.schedule_slots.all(), many=True).data})
        serializer = WeeklyScheduleSerializer(device, data=request.data)
        serializer.is_valid(raise_exception=True); serializer.save()
        dispatch = None
        dispatch_error = None
        try:
            dispatch = dispatch_current_volume(device)
        except OneNETError as exc:
            dispatch_error = str(exc)
        return Response({
            'slots': ScheduleSlotSerializer(device.schedule_slots.all(), many=True).data,
            'currentDispatch': dispatch,
            'dispatchError': dispatch_error,
        })

    @action(detail=True, methods=['get', 'patch'], url_path='audio-config')
    def audio_config(self, request, device_id=None):
        config, _ = AudioConfig.objects.get_or_create(device=self.get_object())
        serializer = AudioConfigSerializer(config, data=request.data, partial=True) if request.method == 'PATCH' else AudioConfigSerializer(config)
        if request.method == 'PATCH': serializer.is_valid(raise_exception=True); serializer.save()
        return Response({
            **serializer.data,
            'delivery': 'local_only',
            'terminalConfirmed': False,
        })

    @action(detail=True, methods=['get'], url_path='protocol')
    def protocol(self, request, device_id=None):
        self.get_object()
        return Response(protocol_manifest())

    @action(detail=True, methods=['post'], url_path='file-transfer/prepare')
    def file_transfer_prepare(self, request, device_id=None):
        self.get_object()
        try:
            result = prepare_file_transfer(
                str(request.data.get('kind', '')),
                str(request.data.get('filename', '')),
                int(request.data.get('size', 0)),
                str(request.data.get('crc32', '')),
            )
        except (TypeError, ValueError) as exc:
            return Response({'detail': str(exc)}, status=400)
        return Response(result)

    @action(detail=True, methods=['post'], url_path='rename-bluetooth')
    def rename_bluetooth(self, request, device_id=None):
        serializer = BluetoothRenameSerializer(data=request.data); serializer.is_valid(raise_exception=True)
        device = self.get_object(); device.bluetooth_name = serializer.validated_data['bluetoothName']; device.save(update_fields=['bluetooth_name', 'updated_at'])
        return Response({
            'bluetoothName': device.bluetooth_name,
            'accepted': True,
            'terminalConfirmed': False,
            'delivery': 'pending_terminal_protocol',
        }, status=status.HTTP_200_OK)

class RegisterView(APIView):
    permission_classes = [AllowAny]
    def post(self, request):
        username = str(request.data.get('username', '')).strip()
        password = str(request.data.get('password', ''))
        if len(username) < 3: return Response({'username': ['用户名至少 3 个字符。']}, status=400)
        if len(password) < 6: return Response({'password': ['密码至少 6 个字符。']}, status=400)
        User = get_user_model()
        if User.objects.filter(username=username).exists(): return Response({'username': ['用户名已存在。']}, status=400)
        user = User.objects.create_user(username=username, password=password)
        token = Token.objects.create(user=user)
        return Response({'token': token.key, 'username': user.username}, status=201)

class LoginView(APIView):
    permission_classes = [AllowAny]
    def post(self, request):
        user = authenticate(username=request.data.get('username'), password=request.data.get('password'))
        if not user: return Response({'detail': '用户名或密码错误。'}, status=400)
        token, _ = Token.objects.get_or_create(user=user)
        return Response({'token': token.key, 'username': user.username})

class MeView(APIView):
    def get(self, request): return Response({'username': request.user.username})

class LogoutView(APIView):
    def post(self, request):
        request.auth.delete()
        return Response(status=204)
