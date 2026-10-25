import base64
import io
import json
import re
import uuid
import wave
import zlib

MAX_FRAME_BYTES = 200
FILE_RAW_CHUNK_BYTES = 96
FILE_KINDS = {'walk', 'rush', 'custom'}

PROPERTY_DEFINITIONS = {
    'DftEnable': {'name': '参数设置使能', 'type': 'int32', 'access': 'rw', 'min': 0, 'max': 1, 'unit': '', 'verified': True},
    'DftVolume': {'name': '喇叭音量', 'type': 'int32', 'access': 'rw', 'min': 0, 'max': 9, 'unit': 'level', 'verified': True},
    'DftStHour': {'name': '工作开始小时', 'type': 'int32', 'access': 'rw', 'min': 0, 'max': 23, 'unit': 'hour', 'verified': True},
    'DftStMinute': {'name': '工作开始分钟', 'type': 'int32', 'access': 'rw', 'min': 0, 'max': 59, 'unit': 'minute', 'verified': True},
    'DtfEdHour': {'name': '工作结束小时', 'type': 'int32', 'access': 'rw', 'min': 0, 'max': 23, 'unit': 'hour', 'verified': True},
    'DftEdMinute': {'name': '工作结束分钟', 'type': 'int32', 'access': 'rw', 'min': 0, 'max': 59, 'unit': 'minute', 'verified': True},
    'Period': {'name': '工作周期（兼容）', 'type': 'int32', 'access': 'rw', 'min': 0, 'max': 3600, 'unit': 'second', 'verified': True, 'deprecated': True},
    'RushTime': {'name': '快行时间（兼容）', 'type': 'int32', 'access': 'rw', 'min': 0, 'max': 3600, 'unit': 'second', 'verified': True, 'deprecated': True},
    'WalkTime': {'name': '慢行时间（兼容）', 'type': 'int32', 'access': 'rw', 'min': 0, 'max': 3600, 'unit': 'second', 'verified': True, 'deprecated': True},
    'ID': {'name': '终端编号', 'type': 'int32', 'access': 'r', 'unit': '', 'verified': True},
    'Noise': {'name': '现场噪声', 'type': 'int32', 'access': 'r', 'unit': 'raw', 'verified': True},
    'State': {'name': '设备状态位图', 'type': 'uint32', 'access': 'r', 'min': 0, 'max': 4294967295, 'unit': 'bitmask', 'verified': True},
}

STATE_BITS = {
    0: '设备异常',
    1: 'GPS异常',
    2: 'RTC电池欠压',
    3: '音频文件异常',
    4: 'Flash写入异常',
    5: '噪声传感器异常',
    6: '功放异常',
    7: '通信模块异常',
    8: '电源异常',
}


def compact_json(payload):
    encoded = json.dumps(payload, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
    if len(encoded) > MAX_FRAME_BYTES:
        raise ValueError(f'通信帧 {len(encoded)} 字节，超过 {MAX_FRAME_BYTES} 字节限制')
    return encoded


def build_command(command_type, request_id, **params):
    payload = {'v': 1, 't': command_type, 'id': request_id, **params}
    compact_json(payload)
    return payload


def build_file_chunk(transfer_id, number, content):
    return build_command('fc', transfer_id, n=number, d=base64.b64encode(content).decode())


def validate_property_values(params):
    unknown = set(params) - set(PROPERTY_DEFINITIONS)
    if unknown:
        raise ValueError(f'不支持的参数字段：{", ".join(sorted(unknown))}')
    for key, value in params.items():
        definition = PROPERTY_DEFINITIONS[key]
        if definition.get('access') != 'rw':
            raise ValueError(f'{key} 为只读字段')
        if type(value) is not int:
            raise ValueError(f'{key} 必须为整数')
        if 'min' in definition and value < definition['min']:
            raise ValueError(f'{key} 不能小于 {definition["min"]}')
        if 'max' in definition and value > definition['max']:
            raise ValueError(f'{key} 不能大于 {definition["max"]}')


def prepare_file_transfer(kind, filename, size, crc32):
    if kind not in FILE_KINDS:
        raise ValueError('文件类型必须为 walk、rush 或 custom')
    if not filename.lower().endswith('.wav'):
        raise ValueError('只允许 WAV 文件')
    if size <= 0:
        raise ValueError('文件大小必须大于 0')
    if not re.fullmatch(r'[0-9A-Fa-f]{8}', crc32):
        raise ValueError('crc32 必须为 8 位十六进制字符串')
    transfer_id = uuid.uuid4().hex[:8]
    total = (size + FILE_RAW_CHUNK_BYTES - 1) // FILE_RAW_CHUNK_BYTES
    begin = {'v': 1, 't': 'fb', 'id': transfer_id, 'k': kind, 's': size, 'n': total, 'c': crc32.lower()}
    compact_json(begin)
    # Validate the worst-case chunk envelope at protocol-definition time.
    sample = {'v': 1, 't': 'fc', 'id': transfer_id, 'n': total - 1, 'd': base64.b64encode(bytes(FILE_RAW_CHUNK_BYTES)).decode()}
    chunk_bytes = len(compact_json(sample))
    return {
        'transferId': transfer_id,
        'rawChunkBytes': FILE_RAW_CHUNK_BYTES,
        'totalChunks': total,
        'maxFrameBytes': MAX_FRAME_BYTES,
        'worstCaseChunkFrameBytes': chunk_bytes,
        'beginFrame': begin,
        'transportReady': False,
        'pending': '等待设备方确认 OneNET 自定义 Topic 与 flash 写入策略',
    }


def validate_wav_bytes(kind, content):
    if kind not in FILE_KINDS:
        raise ValueError('文件类型必须为 walk、rush 或 custom')
    if not content:
        raise ValueError('WAV 文件不能为空')
    try:
        with wave.open(io.BytesIO(content), 'rb') as wav:
            channels = wav.getnchannels()
            sample_rate = wav.getframerate()
            bit_depth = wav.getsampwidth() * 8
            frames = wav.getnframes()
            compression = wav.getcomptype()
    except (EOFError, wave.Error) as exc:
        raise ValueError('无法解析 WAV 文件头') from exc
    duration = frames / sample_rate if sample_rate else 0
    max_duration = 24 if kind == 'custom' else 4
    errors = []
    if compression != 'NONE': errors.append('必须为 PCM 编码')
    if channels != 1: errors.append('必须为单声道')
    if sample_rate != 8000: errors.append('采样率必须为 8000Hz')
    if bit_depth != 8: errors.append('位深必须为 8bit')
    if duration > max_duration + 0.001: errors.append(f'{kind} 时长不能超过 {max_duration} 秒')
    if errors:
        raise ValueError('；'.join(errors))
    return {
        'kind': kind, 'size': len(content), 'duration': round(duration, 3),
        'channels': channels, 'sampleRate': sample_rate, 'bitDepth': bit_depth,
        'crc32': f'{zlib.crc32(content) & 0xffffffff:08x}',
    }


def protocol_manifest():
    return {
        'version': '1.1',
        'encoding': 'UTF-8 compact JSON',
        'maxFrameBytes': MAX_FRAME_BYTES,
        'properties': PROPERTY_DEFINITIONS,
        'stateBits': STATE_BITS,
        'schedule': {
            'platformMode': 'time_point_volume',
            'terminalMode': 'pending_contract',
            'terminalSlotFields': ['seq', 'day', 'start', 'finish', 'volume', 'enable'],
            'overlapPolicy': 'reject',
            'timezoneOwner': 'platform_converts_to_utc',
        },
        'fileTransfer': {
            'status': 'preflight_ready', 'rawChunkBytes': FILE_RAW_CHUNK_BYTES,
            'encoding': 'Base64', 'checksum': 'CRC32', 'kinds': sorted(FILE_KINDS),
            'transportStatus': 'pending_joint_test',
        },
        'bluetooth': {
            'status': 'pending_terminal_protocol', 'maxNameBytes': 32,
            'commands': ['bt_set', 'bt_get', 'bt_info'],
        },
        'streetAudio': {
            'status': 'local_only', 'deliveryModes': ['tts', 'wav'],
            'selectedMode': None,
        },
        'audio': {
            'status': 'server_validation_ready', 'kinds': sorted(FILE_KINDS),
            'commands': ['audio_get', 'audio_info', 'audio_play', 'audio_stop'],
        },
        'signalController': {
            'status': 'requirements_pending',
            'digitalInputsRequired': ['enable', 'green', 'red'],
            'rs485': {'status': 'vendor_protocol_required'},
        },
    }
