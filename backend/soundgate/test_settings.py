from .settings import *  # noqa: F403

# Integration tests must never require permission to create/drop the production
# MySQL database. SQLite keeps the complete DRF flow isolated and disposable.
DATABASES = {  # noqa: F405
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    }
}

PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']
