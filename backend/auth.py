"""Short-lived, signed browser authentication for the private preview."""
import base64
import binascii
import hashlib
import hmac
import secrets
import time

COOKIE_NAME = 'folio_preview_auth'
COOKIE_TTL = 3600

def valid_basic(header, password):
    if not header.lower().startswith('basic '):
        return False
    try:
        provided = base64.b64decode(header[6:], validate=True)
    except (ValueError, binascii.Error):
        return False
    return secrets.compare_digest(provided, ('folio:' + password).encode('utf-8'))

def sign_cookie(password, expires=None):
    expires = str(int(time.time()) + COOKIE_TTL if expires is None else int(expires))
    signature = hmac.new(password.encode('utf-8'), expires.encode('ascii'), hashlib.sha256).hexdigest()
    return expires + '.' + signature

def valid_cookie(value, password):
    if not value or len(value) > 100:
        return False
    try:
        expires, signature = value.split('.', 1)
        now = int(time.time())
        if not now < int(expires) <= now + COOKIE_TTL:
            return False
        expected = sign_cookie(password, int(expires)).split('.', 1)[1]
        return secrets.compare_digest(signature, expected)
    except (ValueError, TypeError, UnicodeError):
        return False
