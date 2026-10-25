from django.db import transaction
from django.conf import settings
from rest_framework import serializers
from .models import AudioConfig, Device, DeviceAudioFile, FileTransfer, ScheduleSlot, SignalInterfaceConfig, TerminalCommand

class DeviceSerializer(serializers.ModelSerializer):
    id = serializers.CharField(source='device_id', read_only=True)
    gps = serializers.CharField(source='get_gps_status_display', read_only=True)
    lastSeen = serializers.DateTimeField(source='last_seen_at', read_only=True)
    cloudConnected = serializers.BooleanField(source='cloud_connected')
    bluetoothName = serializers.CharField(source='bluetooth_name')
    onenetDeviceName = serializers.CharField(source='onenet_device_name', read_only=True)
    streetName = serializers.SerializerMethodField()

    class Meta:
        model = Device
        fields = ['id', 'name', 'online', 'enabled', 'volume', 'lastSeen', 'gps', 'cloudConnected', 'bluetoothName', 'streetName', 'onenetDeviceName']
        read_only_fields = ['id', 'online', 'lastSeen', 'gps', 'cloudConnected', 'bluetoothName', 'streetName']

    def get_streetName(self, obj):
        config, _ = AudioConfig.objects.get_or_create(device=obj)
        return config.street_name

class DeviceCreateSerializer(serializers.ModelSerializer):
    id = serializers.CharField(source='device_id', max_length=64)
    bluetoothName = serializers.CharField(source='bluetooth_name', max_length=32)
    streetName = serializers.CharField(write_only=True, required=False, allow_blank=True, max_length=200)
    onenetDeviceName = serializers.CharField(source='onenet_device_name', max_length=64)

    class Meta:
        model = Device
        fields = ['id', 'name', 'bluetoothName', 'streetName', 'onenetDeviceName']

    def validate_id(self, value):
        value = value.strip()
        if Device.objects.filter(device_id=value).exists(): raise serializers.ValidationError('设备编号已存在。')
        return value

    def create(self, validated_data):
        street_name = validated_data.pop('streetName', '')
        device = Device.objects.create(owner=self.context['request'].user, **validated_data)
        AudioConfig.objects.create(device=device, street_name=street_name)
        return device

class OneNETParametersSerializer(serializers.Serializer):
    DftEdMinute = serializers.IntegerField(required=False, min_value=0, max_value=59)
    DftEnable = serializers.IntegerField(required=False, min_value=0, max_value=1)
    DftStHour = serializers.IntegerField(required=False, min_value=0, max_value=23)
    DftStMinute = serializers.IntegerField(required=False, min_value=0, max_value=59)
    DftVolume = serializers.IntegerField(required=False, min_value=0, max_value=9)
    DtfEdHour = serializers.IntegerField(required=False, min_value=0, max_value=23)
    Period = serializers.IntegerField(required=False, min_value=0, max_value=3600)
    RushTime = serializers.IntegerField(required=False, min_value=0, max_value=3600)
    WalkTime = serializers.IntegerField(required=False, min_value=0, max_value=3600)

    def validate(self, attrs):
        if not attrs: raise serializers.ValidationError('至少提供一个参数。')
        return attrs


class OneNETImportSerializer(serializers.Serializer):
    deviceNames = serializers.ListField(
        child=serializers.CharField(max_length=64),
        min_length=1,
        max_length=100,
    )

    def validate_deviceNames(self, values):
        cleaned = list(dict.fromkeys(value.strip() for value in values if value.strip()))
        if not cleaned:
            raise serializers.ValidationError('至少选择一台设备。')
        return cleaned

class ScheduleSlotSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(required=False)
    time = serializers.TimeField(format='%H:%M')
    class Meta:
        model = ScheduleSlot
        fields = ['id', 'weekday', 'time', 'volume']

class WeeklyScheduleSerializer(serializers.Serializer):
    slots = ScheduleSlotSerializer(many=True)

    def validate_slots(self, slots):
        seen = set()
        counts = {}
        for slot in slots:
            key = (slot['weekday'], slot['time'])
            if key in seen: raise serializers.ValidationError('同一天不能存在重复时间。')
            seen.add(key)
            counts[slot['weekday']] = counts.get(slot['weekday'], 0) + 1
            if counts[slot['weekday']] > settings.MAX_SCHEDULE_SLOTS_PER_DAY:
                raise serializers.ValidationError(f'每天最多 {settings.MAX_SCHEDULE_SLOTS_PER_DAY} 个时段。')
        return slots

    @transaction.atomic
    def update(self, instance, validated_data):
        instance.schedule_slots.all().delete()
        ScheduleSlot.objects.bulk_create([ScheduleSlot(device=instance, **slot) for slot in validated_data['slots']])
        return instance

class AudioConfigSerializer(serializers.ModelSerializer):
    streetName = serializers.CharField(source='street_name', allow_blank=True)
    class Meta:
        model = AudioConfig
        fields = ['streetName', 'walk_file_name', 'rush_file_name', 'custom_file_name', 'file_metadata', 'updated_at']
        read_only_fields = ['walk_file_name', 'rush_file_name', 'custom_file_name', 'file_metadata', 'updated_at']

class BluetoothRenameSerializer(serializers.Serializer):
    bluetoothName = serializers.CharField(max_length=32)
    password = serializers.CharField(write_only=True, trim_whitespace=False)
    def validate_bluetoothName(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError('蓝牙名称不能为空。')
        if len(value.encode('utf-8')) > 32:
            raise serializers.ValidationError('蓝牙名称 UTF-8 编码后不能超过 32 字节。')
        return value
    def validate_password(self, value):
        import secrets
        expected = settings.DEVICE_ADMIN_PASSWORD
        if not secrets.compare_digest(value, expected): raise serializers.ValidationError('管理密码错误。')
        return value


class DeviceAudioFileSerializer(serializers.ModelSerializer):
    fileName = serializers.CharField(source='original_name', read_only=True)
    duration = serializers.SerializerMethodField()
    class Meta:
        model = DeviceAudioFile
        fields = ['id', 'kind', 'fileName', 'size', 'duration', 'crc32', 'metadata', 'created_at']
    def get_duration(self, obj): return obj.duration_ms / 1000


class TerminalCommandSerializer(serializers.ModelSerializer):
    requestId = serializers.CharField(source='request_id', read_only=True)
    terminalConfirmed = serializers.SerializerMethodField()
    class Meta:
        model = TerminalCommand
        fields = ['requestId', 'command_type', 'status', 'attempts', 'response', 'error', 'terminalConfirmed', 'created_at', 'updated_at', 'confirmed_at']
    def get_terminalConfirmed(self, obj): return obj.status == TerminalCommand.Status.SUCCEEDED


class FileTransferSerializer(serializers.ModelSerializer):
    transferId = serializers.CharField(source='transfer_id', read_only=True)
    fileId = serializers.IntegerField(source='audio_file_id', read_only=True)
    progress = serializers.SerializerMethodField()
    terminalConfirmed = serializers.SerializerMethodField()
    class Meta:
        model = FileTransfer
        fields = ['transferId', 'fileId', 'status', 'next_chunk', 'total_chunks', 'progress', 'attempts', 'error', 'terminalConfirmed', 'created_at', 'updated_at', 'confirmed_at']
    def get_progress(self, obj): return round(obj.next_chunk * 100 / obj.total_chunks, 1) if obj.total_chunks else 0
    def get_terminalConfirmed(self, obj): return obj.status == FileTransfer.Status.SUCCEEDED


class SignalInterfaceSerializer(serializers.ModelSerializer):
    class Meta:
        model = SignalInterfaceConfig
        fields = ['mode', 'io_inputs', 'rs485', 'confirmed', 'updated_at']
        read_only_fields = ['confirmed', 'updated_at']

    def validate(self, attrs):
        mode = attrs.get('mode', getattr(self.instance, 'mode', 'io'))
        if mode == 'rs485':
            values = attrs.get('rs485', getattr(self.instance, 'rs485', {}))
            required = {'baudRate', 'dataBits', 'stopBits', 'parity', 'address', 'timeoutMs', 'retries'}
            missing = required - set(values)
            if missing: raise serializers.ValidationError({'rs485': f'缺少字段：{", ".join(sorted(missing))}'})
        return attrs
