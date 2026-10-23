import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / '.env')

SECRET_KEY = os.getenv('DJANGO_SECRET_KEY', 'unsafe-development-key')
DEBUG = os.getenv('DJANGO_DEBUG', 'true').lower() == 'true'
ALLOWED_HOSTS = [v.strip() for v in os.getenv('DJANGO_ALLOWED_HOSTS', '127.0.0.1,localhost').split(',') if v.strip()]

INSTALLED_APPS = [
    'django.contrib.admin', 'django.contrib.auth', 'django.contrib.contenttypes',
    'django.contrib.sessions', 'django.contrib.messages', 'django.contrib.staticfiles',
    'corsheaders', 'rest_framework', 'rest_framework.authtoken', 'devices',
]
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware', 'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware', 'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware', 'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware', 'django.middleware.clickjacking.XFrameOptionsMiddleware',
]
ROOT_URLCONF = 'soundgate.urls'
TEMPLATES = [{'BACKEND': 'django.template.backends.django.DjangoTemplates', 'DIRS': [], 'APP_DIRS': True, 'OPTIONS': {'context_processors': ['django.template.context_processors.request', 'django.contrib.auth.context_processors.auth', 'django.contrib.messages.context_processors.messages']}}]
WSGI_APPLICATION = 'soundgate.wsgi.application'
DATABASES = {'default': {'ENGINE': 'django.db.backends.mysql', 'NAME': os.getenv('MYSQL_DATABASE', 'soundgate'), 'USER': os.getenv('MYSQL_USER', 'soundgate'), 'PASSWORD': os.getenv('MYSQL_PASSWORD', ''), 'HOST': os.getenv('MYSQL_HOST', '127.0.0.1'), 'PORT': os.getenv('MYSQL_PORT', '3306'), 'OPTIONS': {'charset': 'utf8mb4'}}}
AUTH_PASSWORD_VALIDATORS = []
LANGUAGE_CODE = 'zh-hans'
TIME_ZONE = 'Asia/Shanghai'
USE_I18N = True
USE_TZ = True
STATIC_URL = 'static/'
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
CORS_ALLOWED_ORIGINS = [v.strip() for v in os.getenv('CORS_ALLOWED_ORIGINS', 'http://127.0.0.1:5173').split(',') if v.strip()]
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': ['rest_framework.authentication.TokenAuthentication'],
    'DEFAULT_PERMISSION_CLASSES': ['rest_framework.permissions.IsAuthenticated'],
    'DEFAULT_RENDERER_CLASSES': ['rest_framework.renderers.JSONRenderer', 'rest_framework.renderers.BrowsableAPIRenderer'] if DEBUG else ['rest_framework.renderers.JSONRenderer'],
}
MAX_SCHEDULE_SLOTS_PER_DAY = int(os.getenv('MAX_SCHEDULE_SLOTS_PER_DAY', '12'))
DEVICE_ADMIN_PASSWORD = os.getenv('DEVICE_ADMIN_PASSWORD', 'change-this-local-admin-password')
ONENET_PRODUCT_ID = os.getenv('ONENET_PRODUCT_ID', 'your-product-id')
ONENET_USER_ID = os.getenv('ONENET_USER_ID', '')
ONENET_ACCESS_KEY = os.getenv('ONENET_ACCESS_KEY', '')
ONENET_ACCESS_KEY_IS_BASE64 = os.getenv('ONENET_ACCESS_KEY_IS_BASE64', 'false').lower() == 'true'
ONENET_API_KEY = os.getenv('ONENET_API_KEY', '')
ONENET_AUTH_MODE = os.getenv('ONENET_AUTH_MODE', 'auto').lower()
ONENET_DEVICE_TOKEN = os.getenv('ONENET_DEVICE_TOKEN', '')
ONENET_TOKEN_VERSION = os.getenv('ONENET_TOKEN_VERSION', '2018-10-31')
ONENET_TOKEN_METHOD = os.getenv('ONENET_TOKEN_METHOD', 'md5').lower()
ONENET_API_URL = os.getenv('ONENET_API_URL', 'https://iot-api.heclouds.com/thingmodel/set-device-property')
ONENET_PROPERTY_DETAIL_API_URL = os.getenv('ONENET_PROPERTY_DETAIL_API_URL', 'https://iot-api.heclouds.com/thingmodel/query-device-property-detail')
ONENET_DESIRED_API_URL = os.getenv('ONENET_DESIRED_API_URL', 'https://iot-api.heclouds.com/thingmodel/set-device-desired-property')
ONENET_LEGACY_API_BASE = os.getenv('ONENET_LEGACY_API_BASE', 'https://api.heclouds.com')
ONENET_GATEWAY_DEVICE_NAME = os.getenv('ONENET_GATEWAY_DEVICE_NAME', 'your-gateway-device')
ONENET_GATEWAY_DEVICE_ID = os.getenv('ONENET_GATEWAY_DEVICE_ID', '')
ONENET_MQTT_HOST = os.getenv('ONENET_MQTT_HOST', '183.230.102.116')
ONENET_MQTT_PORT = int(os.getenv('ONENET_MQTT_PORT', '25002'))
