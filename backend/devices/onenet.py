import base64
import hashlib
import hmac
import json
import time
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

from django.conf import settings
from .device_protocol import validate_property_values

MAX_FRAME_BYTES = 200
ALLOWED_PARAMS = {
    'DftEdMinute', 'DftEnable', 'DftStHour', 'DftStMinute', 'DftVolume',
    'DtfEdHour', 'Period', 'RushTime', 'WalkTime',
}


class OneNETError(Exception):
    pass


class OneNETNotConfigured(OneNETError):
    pass


def _sign_token(resource, access_key, expires_in=3600, key_is_base64=True):
    version = settings.ONENET_TOKEN_VERSION
    method = settings.ONENET_TOKEN_METHOD
    expires = str(int(time.time()) + expires_in)
    message = f'{expires}\n{method}\n{resource}\n{version}'.encode()
    try:
        key = base64.b64decode(access_key, validate=True) if key_is_base64 else access_key.encode()
    except Exception as exc:
        raise OneNETNotConfigured('OneNET accessKey 不是有效的 Base64。') from exc
    digest = {'md5': hashlib.md5, 'sha1': hashlib.sha1}.get(method)
    if digest is None:
        raise OneNETNotConfigured('OneNET Token 签名算法仅支持 md5 或 sha1。')
    signature = quote(base64.b64encode(hmac.new(key, message, digest).digest()).decode(), safe='')
    return f'version={version}&res={quote(resource, safe="")}&et={expires}&method={method}&sign={signature}'


def generate_token(expires_in=3600):
    if not settings.ONENET_USER_ID or not settings.ONENET_ACCESS_KEY:
        raise OneNETNotConfigured('OneNET userId/accessKey 尚未配置。')
    return _sign_token(
        f'userid/{settings.ONENET_USER_ID}',
        settings.ONENET_ACCESS_KEY,
        expires_in,
        key_is_base64=settings.ONENET_ACCESS_KEY_IS_BASE64,
    )


def generate_device_token(device_name=None, expires_in=3600):
    if settings.ONENET_DEVICE_TOKEN:
        return settings.ONENET_DEVICE_TOKEN
    raise OneNETNotConfigured('OneNET 设备 Token 尚未配置。')


def build_device_frame(device, params):
    try:
        validate_property_values(params)
    except ValueError as exc:
        raise OneNETError(str(exc)) from exc
    frame = {
        'product_id': device.onenet_product_id,
        'device_name': device.onenet_device_name,
        'imei': '',
        'params': params,
    }
    encoded = json.dumps(frame, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
    if len(encoded) > MAX_FRAME_BYTES:
        raise OneNETError(f'MQTT 帧长度 {len(encoded)} 字节，超过 {MAX_FRAME_BYTES} 字节限制。')
    return frame, encoded


def _json_request(url, *, method='GET', body=None, headers=None):
    request = Request(url, data=body, method=method, headers=headers or {})
    try:
        with urlopen(request, timeout=10) as response:
            raw = response.read()
    except HTTPError as exc:
        detail = exc.read().decode(errors='replace')
        raise OneNETError(f'OneNET HTTP {exc.code}: {detail}') from exc
    except URLError as exc:
        raise OneNETError(f'无法连接 OneNET：{exc.reason}') from exc
    try:
        return json.loads(raw.decode())
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise OneNETError('OneNET 返回了无法解析的响应。') from exc


def list_product_devices():
    """Return every real OneNET device under the configured product."""
    query = urlencode({
        'product_id': settings.ONENET_PRODUCT_ID,
        'offset': 0,
        'limit': 100,
    })
    token = generate_token() if settings.ONENET_USER_ID else generate_device_token()
    result = _json_request(
        f'https://iot-api.heclouds.com/device/list?{query}',
        headers={'Authorization': token},
    )
    if result.get('code') not in (None, 0) or result.get('success') is False:
        raise OneNETError(result.get('msg') or 'OneNET 设备列表查询失败。')
    data = result.get('data') or {}
    devices = data.get('list') or data.get('devices') or []
    return devices, (data.get('meta') or {}).get('total', len(devices))


def get_device_snapshot(device_name):
    """Read status and the latest values already reported by one OneNET device."""
    token = generate_token() if settings.ONENET_USER_ID else generate_device_token()
    query = urlencode({
        'product_id': settings.ONENET_PRODUCT_ID,
        'device_name': device_name,
    })
    properties_result = _json_request(
        f'https://iot-api.heclouds.com/thingmodel/query-device-property?{query}',
        headers={'Authorization': token},
    )
    if properties_result.get('code') not in (None, 0) or properties_result.get('success') is False:
        raise OneNETError(properties_result.get('msg') or f'读取设备 {device_name} 属性失败。')
    raw_data = properties_result.get('data') or []
    items = raw_data if isinstance(raw_data, list) else (raw_data.get('list') or raw_data.get('properties') or [])
    params = {}
    latest_time = None
    for item in items:
        identifier = item.get('identifier')
        if identifier not in ALLOWED_PARAMS:
            continue
        value = item.get('value', item.get('current_value', item.get('currentValue')))
        if isinstance(value, dict) and 'value' in value:
            value = value['value']
        if value is not None:
            params[identifier] = value
        item_time = item.get('time')
        if item_time is not None and (latest_time is None or int(item_time) > latest_time):
            latest_time = int(item_time)
    detail_result = _json_request(
        f'https://iot-api.heclouds.com/device/detail?{query}',
        headers={'Authorization': token},
    )
    if detail_result.get('code') not in (None, 0) or detail_result.get('success') is False:
        raise OneNETError(detail_result.get('msg') or f'读取设备 {device_name} 状态失败。')
    detail = detail_result.get('data') or {}
    return {
        'deviceName': device_name,
        'online': detail.get('status') in (1, '1', 'online'),
        'params': params,
        'latestTime': latest_time,
    }


def _get_live_property_values(device_name, identifiers):
    """Actively request current values from the terminal in small MCU-safe batches."""
    token = generate_token() if settings.ONENET_USER_ID else generate_device_token(device_name)
    values = {}
    identifiers = list(identifiers)
    for offset in range(0, len(identifiers), 3):
        batch = identifiers[offset:offset + 3]
        body = json.dumps({
            'product_id': settings.ONENET_PRODUCT_ID,
            'device_name': device_name,
            'params': batch,
        }, separators=(',', ':')).encode()
        result = _json_request(
            settings.ONENET_PROPERTY_DETAIL_API_URL,
            method='POST', body=body,
            headers={'Authorization': token, 'Content-Type': 'application/json'},
        )
        if result.get('code') not in (None, 0) or result.get('success') is False:
            raise OneNETError(result.get('msg') or f'主动读取设备 {device_name} 属性失败。')
        data = result.get('data') or {}
        if isinstance(data, dict):
            values.update(data.get('params') if isinstance(data.get('params'), dict) else data)
    return values


def get_device_parameters(device_name, identifiers=None):
    """Return the real values currently reported by the terminal."""
    token = generate_token() if settings.ONENET_USER_ID else generate_device_token()
    query = urlencode({
        'product_id': settings.ONENET_PRODUCT_ID,
        'device_name': device_name,
    })
    result = _json_request(
        f'https://iot-api.heclouds.com/thingmodel/query-device-property?{query}',
        headers={'Authorization': token},
    )
    if result.get('code') not in (None, 0) or result.get('success') is False:
        raise OneNETError(result.get('msg') or f'读取设备 {device_name} 参数失败。')
    raw_data = result.get('data') or []
    items = raw_data if isinstance(raw_data, list) else (raw_data.get('list') or raw_data.get('properties') or [])
    requested = [key for key in (identifiers or ALLOWED_PARAMS) if key in ALLOWED_PARAMS]
    live_values = _get_live_property_values(device_name, requested)
    parameters = {}
    for item in items:
        identifier = item.get('identifier')
        if identifier not in ALLOWED_PARAMS:
            continue
        reported = live_values.get(identifier)
        parameters[identifier] = {
            'value': reported,
            'displayValue': reported,
            'name': item.get('name', identifier),
            'dataType': item.get('data_type'),
        }
    for identifier in requested:
        if identifier not in parameters:
            parameters[identifier] = {
                'value': live_values.get(identifier), 'displayValue': live_values.get(identifier),
                'name': identifier, 'dataType': 'int32',
            }
    return parameters


def _resolve_gateway_device_id():
    if settings.ONENET_GATEWAY_DEVICE_ID:
        return settings.ONENET_GATEWAY_DEVICE_ID
    query = urlencode({
        'product_id': settings.ONENET_PRODUCT_ID,
        'auth_info': settings.ONENET_GATEWAY_DEVICE_NAME,
        'limit': 100,
    })
    result = _json_request(
        f'{settings.ONENET_LEGACY_API_BASE}/devices?{query}',
        headers={'api-key': settings.ONENET_API_KEY},
    )
    if result.get('errno') != 0:
        raise OneNETError(result.get('error') or '查询 OneNET 网关设备失败。')
    devices = result.get('data', {}).get('devices', [])
    for item in devices:
        if (item.get('auth_info') == settings.ONENET_GATEWAY_DEVICE_NAME
                or item.get('title') == settings.ONENET_GATEWAY_DEVICE_NAME):
            return str(item.get('id'))
    if len(devices) == 1:
        return str(devices[0].get('id'))
    raise OneNETError(
        f'未找到网关设备 {settings.ONENET_GATEWAY_DEVICE_NAME}，'
        '请配置 ONENET_GATEWAY_DEVICE_ID。'
    )


def _send_legacy_command(encoded_frame):
    if not settings.ONENET_API_KEY:
        raise OneNETNotConfigured('OneNET APIKey 尚未配置。')
    gateway_id = _resolve_gateway_device_id()
    query = urlencode({'device_id': gateway_id, 'qos': 1, 'timeout': 30})
    result = _json_request(
        f'{settings.ONENET_LEGACY_API_BASE}/cmds?{query}',
        method='POST',
        body=encoded_frame,
        headers={'api-key': settings.ONENET_API_KEY, 'Content-Type': 'application/json'},
    )
    if result.get('errno') != 0:
        raise OneNETError(result.get('error') or 'OneNET 命令下发失败。')
    return result


def _set_modern_properties(device, params):
    body = json.dumps({
        'product_id': device.onenet_product_id,
        'device_name': device.onenet_device_name,
        'params': params,
    }, separators=(',', ':')).encode()
    token = generate_token() if settings.ONENET_USER_ID else generate_device_token(device.onenet_device_name)
    result = _json_request(
        settings.ONENET_API_URL,
        method='POST',
        body=body,
        headers={'Authorization': token, 'Content-Type': 'application/json'},
    )
    if result.get('code') not in (None, 0) or result.get('success') is False:
        raise OneNETError(result.get('msg') or 'OneNET 属性设置失败。')
    return result


def _set_device_desired_properties(device, params):
    body = json.dumps({
        'product_id': device.onenet_product_id,
        'device_name': device.onenet_device_name,
        'params': params,
    }, separators=(',', ':')).encode()
    result = _json_request(
        settings.ONENET_DESIRED_API_URL,
        method='POST',
        body=body,
        headers={
            'Authorization': generate_device_token(settings.ONENET_GATEWAY_DEVICE_NAME),
            'Content-Type': 'application/json',
        },
    )
    if result.get('code') not in (None, 0) or result.get('success') is False:
        raise OneNETError(result.get('msg') or 'OneNET 属性期望值设置失败。')
    return result


def set_device_properties(device, params):
    if not device.onenet_device_name:
        raise OneNETError('设备未配置 OneNET device_name。')
    frame, encoded = build_device_frame(device, params)
    mode = settings.ONENET_AUTH_MODE
    if mode == 'api_key' or (mode == 'auto' and settings.ONENET_API_KEY):
        result = _send_legacy_command(encoded)
        transport = 'legacy_command'
    else:
        result = _set_modern_properties(device, params)
        transport = 'device_property'
    return {
        'accepted': True,
        'terminalConfirmed': False,
        'applied': {},
        'frame': frame,
        'frameBytes': len(encoded),
        'transport': transport,
        'response': result,
    }
