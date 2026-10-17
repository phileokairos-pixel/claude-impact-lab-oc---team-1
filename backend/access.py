"""LOOP-06: identity, roles and authorization policy for the shared-record service.

What is real here: server-side checks on every shared-record route, default deny, and institution
scoping. What is NOT here: a production identity provider. Modes:

* `local-prototype` (default): no authentication exists. The shared service stays OFF in this mode,
  because shared records without identity are exactly what this ticket forbids.
* `dev-sessions`: users and hashed bearer tokens from a local JSON file outside Git. For rehearsal and
  tests only. It is NOT production authentication (no expiry, rotation, MFA or revocation).
* `oidc`: BLOCKED until IHH decides on an identity provider. Selecting it reports `blocked`; it never
  falls back to something weaker.

A role sent in request JSON, a header other than the bearer token, or a UI role switch is never trusted.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

ROLES = ('ihh-admin', 'ihh-staff', 'hospital-staff', 'client')
ID_RE = re.compile(r'^[A-Za-z0-9_.-]{1,64}$')
IHH_INSTITUTION = 'ihh'

# action -> roles that may EVER perform it. Record-level checks (institution, assignment, person) still apply.
PERMISSIONS: dict[str, tuple[str, ...]] = {
    'create_person': ('ihh-admin', 'ihh-staff', 'hospital-staff'),
    'create_referral': ('ihh-admin', 'ihh-staff', 'hospital-staff'),
    'list_referrals': ('ihh-admin', 'ihh-staff', 'hospital-staff'),
    'view_referral': ('ihh-admin', 'ihh-staff', 'hospital-staff'),
    'view_internal': ('ihh-admin', 'ihh-staff'),
    'update_shared': ('ihh-admin', 'ihh-staff', 'hospital-staff'),
    'update_internal': ('ihh-admin', 'ihh-staff'),
    'upload_document': ('ihh-admin', 'ihh-staff', 'hospital-staff'),
    'download_document': ('ihh-admin', 'ihh-staff', 'hospital-staff'),
    'export': ('ihh-admin', 'ihh-staff'),
    'manage_tasks': ('ihh-admin', 'ihh-staff'),
    'assign': ('ihh-admin',),
    'delete_referral': ('ihh-admin',),
    'propose_merge': ('ihh-admin', 'ihh-staff'),
    'confirm_merge': ('ihh-admin',),
    'read_audit': ('ihh-admin',),
    'purge_expired': ('ihh-admin',),
    'view_client_summary': ('client',),
}


@dataclass(frozen=True)
class Identity:
    user_id: str
    display_name: str
    institution_id: str
    role: str
    person_id: str | None = None      # only for role == 'client'

    @property
    def is_ihh(self) -> bool:
        return self.role in ('ihh-admin', 'ihh-staff')

    def public(self) -> dict:
        return {'userId': self.user_id, 'displayName': self.display_name, 'institutionId': self.institution_id,
                'role': self.role, 'personId': self.person_id}


def allowed(identity: Identity | None, action: str) -> bool:
    return identity is not None and identity.role in PERMISSIONS.get(action, ())


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode('utf-8')).hexdigest()


@dataclass(frozen=True)
class AuthStatus:
    mode: str
    ready: bool
    blocked_by: str | None = None
    message: str = ''


class AuthProvider:
    """Resolve an Authorization header to an Identity or None. Never raises on bad credentials."""
    mode = 'none'

    def status(self) -> AuthStatus:
        raise NotImplementedError

    def authenticate(self, headers: Mapping[str, str]) -> Identity | None:
        return None


class LocalPrototype(AuthProvider):
    mode = 'local-prototype'

    def status(self):
        return AuthStatus(self.mode, False, 'authentication_not_configured',
                          'No authentication is configured, so shared records are disabled. Set IHH_AUTH_MODE=dev-sessions for rehearsal.')


class OidcBlocked(AuthProvider):
    mode = 'oidc'

    def status(self):
        return AuthStatus(self.mode, False, 'identity_provider_decision',
                          'Blocked: IHH has not chosen an identity provider, so no production login is implemented or simulated.')


class DevSessions(AuthProvider):
    """Bearer tokens hashed in a JSON file: {"users": [{"userId","displayName","institutionId","role","tokenSha256","personId"?}]}.
    NOT production authentication."""
    mode = 'dev-sessions'

    def __init__(self, users: list[dict]):
        self.problems: list[str] = []
        self.by_hash: dict[str, Identity] = {}
        seen = set()
        for u in users:
            try:
                ident = Identity(u['userId'], u.get('displayName', u['userId'])[:80], u['institutionId'], u['role'], u.get('personId'))
                digest = u['tokenSha256']
            except (KeyError, TypeError):
                self.problems.append('A user entry is incomplete.')
                continue
            if ident.role not in ROLES or not ID_RE.match(ident.user_id) or not ID_RE.match(ident.institution_id) \
                    or not re.fullmatch(r'[0-9a-f]{64}', str(digest)) or ident.user_id in seen:
                self.problems.append(f'User {str(ident.user_id)[:20]} is invalid or duplicated.')
                continue
            if ident.is_ihh != (ident.institution_id == IHH_INSTITUTION) or (ident.role == 'client') != bool(ident.person_id):
                self.problems.append(f'User {ident.user_id} has an inconsistent institution, role or person.')
                continue
            seen.add(ident.user_id)
            self.by_hash[digest] = ident

    def status(self):
        if not self.by_hash:
            return AuthStatus(self.mode, False, 'no_valid_users', 'The dev users file has no valid users. ' + ' '.join(self.problems))
        return AuthStatus(self.mode, True, None, 'Development sessions only. This is not production authentication.')

    def authenticate(self, headers):
        value = headers.get('authorization', '')
        scheme, _, token = value.partition(' ')
        if scheme.lower() != 'bearer' or not token.strip():
            return None
        probe = hash_token(token.strip())
        match = None
        for digest, ident in self.by_hash.items():     # compare against all: no early exit on a prefix match
            if hmac.compare_digest(digest, probe):
                match = ident
        return match


def provider_from_env(env: Mapping[str, str] | None = None) -> AuthProvider:
    env = os.environ if env is None else env
    mode = (env.get('IHH_AUTH_MODE') or 'local-prototype').strip()
    if mode == 'oidc':
        return OidcBlocked()
    if mode == 'dev-sessions':
        path = (env.get('IHH_DEV_USERS_FILE') or '').strip()
        try:
            users = json.loads(Path(path).read_text(encoding='utf-8'))['users'] if path else []
        except (OSError, ValueError, KeyError, TypeError):
            users = []
        return DevSessions(users)
    return LocalPrototype()
