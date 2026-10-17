"""Opt-in shared synthetic demo boundary; not staff authentication or patient hosting."""
import base64
import binascii
import os
import re
import secrets
from dataclasses import dataclass

# Exactly the two reviewed, authored training PDFs. No runtime document discovery.
TRAINING_HASHES = frozenset({
    '35156ba45785dd6a93b46f1dd31e576e6b052c7009c31ef3ccb2e78f86d1e579',
    'ce0e44a0c53d131369ae1552a97668db4ff4d5849ac97a59cb2ce8829833b9a0',
})


@dataclass(frozen=True)
class DemoHosting:
    enabled: bool = False
    hostname: str = ''
    password: str = ''

    @classmethod
    def from_env(cls):
        if os.environ.get('CAREWARD_PUBLIC_DEMO') != '1':
            return cls()
        hostname = os.environ.get('RENDER_EXTERNAL_HOSTNAME', '').lower()
        password = os.environ.get('CAREWARD_DEMO_PASSWORD', '')
        if not re.fullmatch(r'[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?', hostname) or '.' not in hostname:
            raise RuntimeError('Protected demo requires RENDER_EXTERNAL_HOSTNAME as a hostname without a scheme or path.')
        if len(password) < 24:
            raise RuntimeError('Protected demo requires CAREWARD_DEMO_PASSWORD with at least 24 characters.')
        return cls(True, hostname, password)

    def authorized(self, header):
        try:
            scheme, value = (header or '').split(' ', 1)
            if scheme.lower() != 'basic':
                return False
            decoded = base64.b64decode(value, validate=True).decode('utf-8')
            username, password = decoded.split(':', 1)
            return secrets.compare_digest(username, 'careward') and secrets.compare_digest(password.encode(), self.password.encode())
        except (ValueError, UnicodeError, binascii.Error):
            return False
