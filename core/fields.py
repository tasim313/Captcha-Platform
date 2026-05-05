from cryptography.fernet import Fernet
from django.conf import settings
from django.db import models
import base64

def get_fernet_key():
    # Derive a 32-byte URL-safe key from Django's SECRET_KEY
    secret = settings.SECRET_KEY.encode()
    return base64.urlsafe_b64encode(secret[:32].ljust(32, b'0'))

class EncryptedField(models.TextField):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fernet = Fernet(get_fernet_key())

    def from_db_value(self, value, expression, connection):
        if value is None:
            return value
        try:
            return self.fernet.decrypt(value.encode()).decode()
        except Exception:
            return value

    def to_python(self, value):
        if isinstance(value, str) and not value.startswith('gAAAA'):
            return value
        return self.from_db_value(value, None, None)

    def get_prep_value(self, value):
        if value is None:
            return value
        return self.fernet.encrypt(value.encode()).decode()