"""LOOP-06: authenticated, institution-scoped shared referral records (synthetic prototype).

Separate from the local OCR/review flow in backend/app.py, which is unchanged. Mounted under
`/api/shared` and active only when an auth provider is ready AND `IHH_SHARED_STORE_DIR` is set.

Data layers per referral, enforced server-side:
  shared   : visible to the referring hospital's staff and to IHH staff
  internal : IHH staff only (internal notes, background-check style content). Never sent to hospitals or clients
  client   : a separate allowlisted summary, written explicitly by IHH staff; not derived from the others
Not-visible referrals/documents answer 404 (not 403), so existence is not leaked across institutions.

Storage: SQLite (stdlib, WAL) plus document bytes under `<store>/documents` (dir 0700, files 0600),
never served statically. The audit log holds IDs and outcome codes only, never note text or file names.
Synthetic data only. This is readiness work: hosting, identity provider, retention period and backup
destination are decisions for IHH (docs/shared-records-readiness.md).
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import secrets
import sqlite3
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field

from backend.access import ID_RE, IHH_INSTITUTION, AuthProvider, Identity, allowed, provider_from_env

log = logging.getLogger('ihh.shared')
MAX_DOC_BYTES = 25 * 1024 * 1024
STATUSES = ('received', 'in-review', 'info-requested', 'handoff', 'closed')
CLIENT_LABELS = ('We received your referral', 'Someone is reviewing it', 'We need a little more information',
                 'Your next step is ready', 'This referral is closed')
SCHEMA = '''
CREATE TABLE IF NOT EXISTS persons(person_id TEXT PRIMARY KEY, institution_id TEXT NOT NULL, label TEXT NOT NULL,
  merged_into TEXT, created_by TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS referrals(referral_id TEXT PRIMARY KEY, person_id TEXT NOT NULL, source_institution_id TEXT NOT NULL,
  version INTEGER NOT NULL, status TEXT NOT NULL, title TEXT NOT NULL, shared_note TEXT NOT NULL, internal_note TEXT NOT NULL,
  client_label TEXT, client_next_step TEXT, assigned TEXT NOT NULL DEFAULT '[]',
  created_by TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS documents(document_id TEXT PRIMARY KEY, referral_id TEXT NOT NULL, group_id TEXT NOT NULL,
  version INTEGER NOT NULL, visibility TEXT NOT NULL, label TEXT NOT NULL, sha256 TEXT NOT NULL, size INTEGER NOT NULL,
  uploaded_by TEXT NOT NULL, uploaded_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS tasks(task_id TEXT PRIMARY KEY, referral_id TEXT NOT NULL, title TEXT NOT NULL, status TEXT NOT NULL,
  version INTEGER NOT NULL, created_by TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS merge_proposals(proposal_id TEXT PRIMARY KEY, from_person_id TEXT NOT NULL, into_person_id TEXT NOT NULL,
  state TEXT NOT NULL, proposed_by TEXT NOT NULL, decided_by TEXT, created_at TEXT NOT NULL, decided_at TEXT);
CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY AUTOINCREMENT, at TEXT NOT NULL, actor_id TEXT NOT NULL,
  institution_id TEXT NOT NULL, role TEXT NOT NULL, action TEXT NOT NULL, referral_id TEXT, outcome TEXT NOT NULL, code TEXT);
'''


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def new_id(prefix: str) -> str:
    return f'{prefix}_{secrets.token_hex(12)}'


class NotVisible(Exception):
    pass


class SharedService:
    def __init__(self, store_dir: Path, provider: AuthProvider, retention_days: int | None = None,
                 clock: Callable[[], str] = now_iso):
        self.provider, self.retention_days, self.clock = provider, retention_days, clock
        self.root = Path(store_dir)
        self.docs = self.root / 'documents'
        self.docs.mkdir(parents=True, exist_ok=True)
        for folder in (self.root, self.docs):
            os.chmod(folder, 0o700)
        self.lock = threading.RLock()
        self.db = sqlite3.connect(self.root / 'shared.sqlite3', check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.execute('PRAGMA foreign_keys=ON')
        self.db.executescript(SCHEMA)
        self.db.commit()

    def close(self):
        with self.lock:
            self.db.close()

    # ---- helpers
    def q(self, sql, *args):
        return self.db.execute(sql, args)

    def audit(self, who: Identity | None, action: str, referral_id: str | None, outcome: str, code: str | None = None):
        with self.lock:
            self.q('INSERT INTO audit(at,actor_id,institution_id,role,action,referral_id,outcome,code) VALUES(?,?,?,?,?,?,?,?)',
                   self.clock(), who.user_id if who else 'anonymous', who.institution_id if who else '-',
                   who.role if who else '-', action, referral_id, outcome, code)
            self.db.commit()

    def resolve_person(self, person_id: str | None) -> str | None:
        for _ in range(20):                 # bounded: a merge chain can never loop forever
            row = self.q('SELECT merged_into FROM persons WHERE person_id=?', person_id).fetchone()
            if row is None or not row['merged_into']:
                return person_id
            person_id = row['merged_into']
        return person_id

    def can_see(self, who: Identity, ref: sqlite3.Row) -> bool:
        if who.role == 'ihh-admin':
            return True
        if who.role == 'ihh-staff':
            return who.user_id in json.loads(ref['assigned'])
        if who.role == 'hospital-staff':
            return ref['source_institution_id'] == who.institution_id
        return False

    def referral_for(self, who: Identity, referral_id: str) -> sqlite3.Row:
        if not ID_RE.match(referral_id or ''):
            raise NotVisible
        ref = self.q('SELECT * FROM referrals WHERE referral_id=?', referral_id).fetchone()
        if ref is None or not self.can_see(who, ref):
            raise NotVisible
        return ref

    def person_visible(self, who: Identity, person_id: str) -> bool:
        row = self.q('SELECT institution_id, created_by FROM persons WHERE person_id=?', person_id).fetchone()
        if row is None:
            return False
        if who.role == 'ihh-admin':
            return True
        if who.role == 'hospital-staff':
            return row['institution_id'] == who.institution_id
        if who.role == 'ihh-staff':     # their own entries, or a person on a referral assigned to them
            return row['created_by'] == who.user_id or any(
                who.user_id in json.loads(r['assigned']) for r in self.q('SELECT assigned FROM referrals WHERE person_id=?', person_id))
        return False

    # ---- views
    def view(self, who: Identity, ref: sqlite3.Row) -> dict:
        out = {'referralId': ref['referral_id'], 'personId': self.resolve_person(ref['person_id']),
               'sourceInstitutionId': ref['source_institution_id'], 'version': ref['version'], 'status': ref['status'],
               'title': ref['title'], 'sharedNote': ref['shared_note'], 'createdAt': ref['created_at'], 'updatedAt': ref['updated_at']}
        internal = allowed(who, 'view_internal')
        if internal:
            out.update(internalNote=ref['internal_note'], assignedStaff=json.loads(ref['assigned']),
                       clientSummary={'statusLabel': ref['client_label'], 'nextStep': ref['client_next_step']})
        out['documents'] = self.documents(ref['referral_id'], internal)
        if internal:
            out['tasks'] = [dict(t) for t in self.q('SELECT task_id AS taskId,title,status,version FROM tasks WHERE referral_id=? ORDER BY created_at',
                                                    ref['referral_id'])]
        return out

    def documents(self, referral_id: str, internal: bool) -> list[dict]:
        rows = self.q('SELECT document_id,group_id,version,visibility,label,sha256,size,uploaded_at FROM documents WHERE referral_id=? ORDER BY group_id,version',
                      referral_id).fetchall()
        return [{'documentId': r['document_id'], 'groupId': r['group_id'], 'version': r['version'], 'visibility': r['visibility'],
                 'label': r['label'], 'sha256': r['sha256'], 'size': r['size'], 'uploadedAt': r['uploaded_at']}
                for r in rows if internal or r['visibility'] == 'shared']

    # ---- retention / deletion
    def delete_referral(self, referral_id: str) -> int:
        """Hard delete: rows and document bytes. The audit log keeps IDs and codes only."""
        with self.lock:
            paths = [r['document_id'] for r in self.q('SELECT document_id FROM documents WHERE referral_id=?', referral_id)]
            for doc_id in paths:
                (self.docs / f'{doc_id}.bin').unlink(missing_ok=True)
            self.q('DELETE FROM documents WHERE referral_id=?', referral_id)
            self.q('DELETE FROM tasks WHERE referral_id=?', referral_id)
            self.q('DELETE FROM referrals WHERE referral_id=?', referral_id)
            self.db.commit()
            return len(paths)

    def purge_expired(self) -> list[str]:
        if not self.retention_days:
            return []
        cutoff = (datetime.fromisoformat(self.clock()) - timedelta(days=self.retention_days)).isoformat(timespec='seconds')
        with self.lock:
            ids = [r['referral_id'] for r in self.q("SELECT referral_id FROM referrals WHERE status='closed' AND updated_at < ?", cutoff)]
            for rid in ids:
                self.delete_referral(rid)
            return ids

    # ---- backup / restore
    def backup(self, dest: Path) -> None:
        dest = Path(dest)
        if dest.exists() and any(dest.iterdir()):
            raise FileExistsError('Backup destination must be empty.')
        (dest / 'documents').mkdir(parents=True, exist_ok=True)
        os.chmod(dest, 0o700)
        with self.lock:
            target = sqlite3.connect(dest / 'shared.sqlite3')
            try:
                self.db.backup(target)
            finally:
                target.close()
            for f in self.docs.glob('*.bin'):
                data = f.read_bytes()
                out = dest / 'documents' / f.name
                out.write_bytes(data)
                os.chmod(out, 0o600)


# --------------------------------------------------------------------------- API

class _Strict(BaseModel):
    model_config = ConfigDict(extra='forbid')


class PersonIn(_Strict):
    label: str = Field(min_length=1, max_length=120)          # a pseudonymous label; do not enter real identifiers


class ReferralIn(_Strict):
    personId: str
    title: str = Field(min_length=1, max_length=120)
    sharedNote: str = Field(default='', max_length=2000)
    sourceInstitutionId: str | None = None                      # IHH staff only; hospital staff always use their own


class ReferralPatch(_Strict):
    version: int = Field(ge=1)
    title: str | None = Field(default=None, min_length=1, max_length=120)
    sharedNote: str | None = Field(default=None, max_length=2000)
    status: Literal['received', 'in-review', 'info-requested', 'handoff', 'closed'] | None = None
    internalNote: str | None = Field(default=None, max_length=2000)
    clientStatusLabel: Literal['We received your referral', 'Someone is reviewing it', 'We need a little more information',
                               'Your next step is ready', 'This referral is closed'] | None = None
    clientNextStep: str | None = Field(default=None, max_length=500)


INTERNAL_FIELDS = {'status', 'internalNote', 'clientStatusLabel', 'clientNextStep'}


class AssignIn(_Strict):
    version: int = Field(ge=1)
    staff: list[str] = Field(max_length=20)


class TaskIn(_Strict):
    title: str = Field(min_length=1, max_length=200)


class TaskPatch(_Strict):
    version: int = Field(ge=1)
    status: Literal['open', 'done', 'blocked']


class MergeIn(_Strict):
    fromPersonId: str
    intoPersonId: str


class MergeConfirm(_Strict):
    confirm: Literal[True]          # explicit human confirmation; absent or false is a 422


def build_router(get_service: Callable[[], SharedService | None], provider: AuthProvider) -> APIRouter:
    router = APIRouter(prefix='/api/shared')

    def session(request: Request):
        """Runs before body validation, so an unauthenticated caller learns nothing about request schemas."""
        service = get_service()
        status = provider.status()
        if service is None or not status.ready:
            raise HTTPException(503, status.message if not status.ready else 'The shared store is not configured (IHH_SHARED_STORE_DIR).')
        if provider.authenticate(request.headers) is None:
            service.audit(None, 'request', None, 'denied', 'unauthenticated')
            raise HTTPException(401, 'Sign in required.')

    secured = APIRouter(dependencies=[Depends(session)])

    def ctx(request: Request, action: str):
        service = get_service()
        status = provider.status()
        if service is None or not status.ready:
            raise HTTPException(503, status.message if not status.ready else 'The shared store is not configured (IHH_SHARED_STORE_DIR).')
        who = provider.authenticate(request.headers)
        if who is None:
            raise HTTPException(401, 'Sign in required.')
        if not allowed(who, action):
            service.audit(who, action, None, 'denied', 'role')
            raise HTTPException(403, 'Your role cannot do this.')
        return service, who

    def hidden(service, who, action, referral_id, code='not_visible'):
        service.audit(who, action, referral_id, 'denied', code)
        return HTTPException(404, 'Not found.')

    @router.get('/status')
    def status():
        s = provider.status()
        return {'mode': s.mode, 'ready': s.ready and get_service() is not None, 'blockedBy': s.blocked_by if not s.ready else (
            None if get_service() is not None else 'shared_store_not_configured'), 'message': s.message,
            'productionReady': False}

    @router.get('/me')
    def me(request: Request):
        service = get_service()
        who = provider.authenticate(request.headers) if service is not None and provider.status().ready else None
        if who is None:
            raise HTTPException(401, 'Sign in required.')
        return who.public()

    @secured.post('/persons', status_code=201)
    def create_person(body: PersonIn, request: Request):
        service, who = ctx(request, 'create_person')
        with service.lock:
            pid = new_id('per')
            service.q('INSERT INTO persons VALUES(?,?,?,NULL,?,?)', pid, who.institution_id, body.label, who.user_id, service.clock())
            service.db.commit()
        service.audit(who, 'create_person', None, 'allowed')
        return {'personId': pid, 'institutionId': who.institution_id}

    @secured.post('/referrals', status_code=201)
    def create_referral(body: ReferralIn, request: Request):
        service, who = ctx(request, 'create_referral')
        with service.lock:
            if not ID_RE.match(body.personId) or not service.person_visible(who, body.personId):
                raise hidden(service, who, 'create_referral', None, 'person_not_visible')
            if who.role == 'hospital-staff':
                source = who.institution_id
                if body.sourceInstitutionId not in (None, source):
                    service.audit(who, 'create_referral', None, 'denied', 'other_institution')
                    raise HTTPException(403, 'Hospital staff can only create referrals for their own institution.')
            else:
                source = body.sourceInstitutionId or ''
                if not ID_RE.match(source) or source == IHH_INSTITUTION:
                    raise HTTPException(422, 'Name the referring institution.')
            rid, now = new_id('ref'), service.clock()
            service.q('INSERT INTO referrals VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)', rid, body.personId, source, 1, 'received', body.title,
                      body.sharedNote, '', CLIENT_LABELS[0], '', json.dumps([who.user_id] if who.role == 'ihh-staff' else []),
                      who.user_id, now, now)
            service.db.commit()
            ref = service.q('SELECT * FROM referrals WHERE referral_id=?', rid).fetchone()
            service.audit(who, 'create_referral', rid, 'allowed')
            return service.view(who, ref)

    @secured.get('/referrals')
    def list_referrals(request: Request):
        service, who = ctx(request, 'list_referrals')
        with service.lock:
            rows = [r for r in service.q('SELECT * FROM referrals ORDER BY created_at') if service.can_see(who, r)]
            service.audit(who, 'list_referrals', None, 'allowed')
            return {'referrals': [{'referralId': r['referral_id'], 'title': r['title'], 'status': r['status'],
                                   'version': r['version'], 'updatedAt': r['updated_at'],
                                   'sourceInstitutionId': r['source_institution_id']} for r in rows]}

    @secured.get('/referrals/{referral_id}')
    def get_referral(referral_id: str, request: Request):
        service, who = ctx(request, 'view_referral')
        with service.lock:
            try:
                ref = service.referral_for(who, referral_id)
            except NotVisible:
                raise hidden(service, who, 'view_referral', referral_id)
            service.audit(who, 'view_referral', referral_id, 'allowed')
            return service.view(who, ref)

    @secured.patch('/referrals/{referral_id}')
    def patch_referral(referral_id: str, body: ReferralPatch, request: Request):
        service, who = ctx(request, 'update_shared')
        with service.lock:
            try:
                ref = service.referral_for(who, referral_id)
            except NotVisible:
                raise hidden(service, who, 'update_referral', referral_id)
            sent = body.model_dump(exclude_unset=True, exclude={'version'})
            if INTERNAL_FIELDS & set(sent) and not allowed(who, 'update_internal'):
                service.audit(who, 'update_referral', referral_id, 'denied', 'field_not_permitted')
                raise HTTPException(403, 'Your role cannot change those fields.')
            if body.version != ref['version']:
                service.audit(who, 'update_referral', referral_id, 'denied', 'stale')
                raise HTTPException(409, 'This referral changed. Reload the latest version.')
            columns = {'title': 'title', 'sharedNote': 'shared_note', 'status': 'status', 'internalNote': 'internal_note',
                       'clientStatusLabel': 'client_label', 'clientNextStep': 'client_next_step'}
            for key, value in sent.items():
                service.q(f'UPDATE referrals SET {columns[key]}=? WHERE referral_id=?', value, referral_id)
            service.q('UPDATE referrals SET version=version+1, updated_at=? WHERE referral_id=?', service.clock(), referral_id)
            service.db.commit()
            service.audit(who, 'update_referral', referral_id, 'allowed')
            return service.view(who, service.q('SELECT * FROM referrals WHERE referral_id=?', referral_id).fetchone())

    @secured.post('/referrals/{referral_id}/assign')
    def assign(referral_id: str, body: AssignIn, request: Request):
        service, who = ctx(request, 'assign')
        if not all(ID_RE.match(s) for s in body.staff):
            raise HTTPException(422, 'Invalid staff ID.')
        with service.lock:
            ref = service.q('SELECT * FROM referrals WHERE referral_id=?', referral_id).fetchone() if ID_RE.match(referral_id) else None
            if ref is None:
                raise hidden(service, who, 'assign', referral_id)
            if body.version != ref['version']:
                service.audit(who, 'assign', referral_id, 'denied', 'stale')
                raise HTTPException(409, 'This referral changed. Reload the latest version.')
            service.q('UPDATE referrals SET assigned=?, version=version+1, updated_at=? WHERE referral_id=?',
                      json.dumps(sorted(set(body.staff))), service.clock(), referral_id)
            service.db.commit()
            service.audit(who, 'assign', referral_id, 'allowed')
            return service.view(who, service.q('SELECT * FROM referrals WHERE referral_id=?', referral_id).fetchone())

    @secured.get('/referrals/{referral_id}/client-summary')
    def client_summary(referral_id: str, request: Request):
        service, who = ctx(request, 'view_client_summary')
        with service.lock:
            ref = service.q('SELECT * FROM referrals WHERE referral_id=?', referral_id).fetchone() if ID_RE.match(referral_id) else None
            mine = ref is not None and service.resolve_person(ref['person_id']) == service.resolve_person(who.person_id)
            if not mine:
                raise hidden(service, who, 'view_client_summary', referral_id)
            service.audit(who, 'view_client_summary', referral_id, 'allowed')
            # Allowlist: exactly these keys. Nothing from shared or internal layers is copied by field name.
            return {'referralId': ref['referral_id'], 'statusLabel': ref['client_label'], 'nextStep': ref['client_next_step'],
                    'updatedAt': ref['updated_at']}

    @secured.post('/referrals/{referral_id}/documents', status_code=201)
    async def upload_document(referral_id: str, request: Request, file: UploadFile = File(...), label: str = Form('document'),
                              visibility: str = Form('shared'), supersedes: str | None = Form(None)):
        service, who = ctx(request, 'upload_document')
        data = await file.read(MAX_DOC_BYTES + 1)
        if len(data) > MAX_DOC_BYTES:
            raise HTTPException(413, 'Document exceeds 25 MB.')
        if not data.startswith(b'%PDF-'):
            raise HTTPException(422, 'Only PDF documents are accepted.')
        if visibility not in ('shared', 'internal') or not re.fullmatch(r'[A-Za-z0-9 _.-]{1,80}', label):
            raise HTTPException(422, 'Invalid label or visibility.')
        with service.lock:
            try:
                ref = service.referral_for(who, referral_id)
            except NotVisible:
                raise hidden(service, who, 'upload_document', referral_id)
            if visibility == 'internal' and not allowed(who, 'view_internal'):
                service.audit(who, 'upload_document', referral_id, 'denied', 'visibility')
                raise HTTPException(403, 'Your role cannot upload internal documents.')
            group, version = new_id('grp'), 1
            if supersedes:
                prior = service.q('SELECT * FROM documents WHERE document_id=? AND referral_id=?', supersedes, referral_id).fetchone() \
                    if ID_RE.match(supersedes) else None
                if prior is None or (prior['visibility'] == 'internal' and not allowed(who, 'view_internal')):
                    raise hidden(service, who, 'upload_document', referral_id, 'prior_not_visible')
                latest = service.q('SELECT MAX(version) AS v FROM documents WHERE group_id=?', prior['group_id']).fetchone()['v']
                group, version = prior['group_id'], latest + 1
            doc_id = new_id('doc')
            path = service.docs / f'{doc_id}.bin'
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, 'wb') as handle:
                handle.write(data)
            service.q('INSERT INTO documents VALUES(?,?,?,?,?,?,?,?,?,?)', doc_id, referral_id, group, version, visibility, label,
                      hashlib.sha256(data).hexdigest(), len(data), who.user_id, service.clock())
            service.db.commit()
            service.audit(who, 'upload_document', referral_id, 'allowed')
            return {'documentId': doc_id, 'groupId': group, 'version': version, 'visibility': visibility}

    @secured.get('/referrals/{referral_id}/documents/{document_id}')
    def download_document(referral_id: str, document_id: str, request: Request):
        service, who = ctx(request, 'download_document')
        with service.lock:
            try:
                service.referral_for(who, referral_id)
            except NotVisible:
                raise hidden(service, who, 'download_document', referral_id)
            doc = service.q('SELECT * FROM documents WHERE document_id=? AND referral_id=?', document_id, referral_id).fetchone() \
                if ID_RE.match(document_id) else None
            if doc is None or (doc['visibility'] == 'internal' and not allowed(who, 'view_internal')):
                raise hidden(service, who, 'download_document', referral_id, 'document_not_visible')
            path = service.docs / f'{doc["document_id"]}.bin'
            if not path.is_file():
                raise HTTPException(404, 'Not found.')
            body = path.read_bytes()
            service.audit(who, 'download_document', referral_id, 'allowed')
        return Response(body, media_type='application/pdf', headers={'Content-Disposition': 'attachment; filename="document.pdf"',
                                                                     'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff'})

    @secured.get('/referrals/{referral_id}/export')
    def export(referral_id: str, request: Request):
        service, who = ctx(request, 'export')
        with service.lock:
            try:
                ref = service.referral_for(who, referral_id)
            except NotVisible:
                raise hidden(service, who, 'export', referral_id)
            service.audit(who, 'export', referral_id, 'allowed')
            return {'mode': 'shared-record-export', 'sent': False, 'exportedBy': who.user_id, 'exportedAt': service.clock(),
                    'record': service.view(who, ref),
                    'notes': ['Synthetic prototype data. Nothing was sent. Not an admission or insurance decision.']}

    @secured.post('/referrals/{referral_id}/tasks', status_code=201)
    def create_task(referral_id: str, body: TaskIn, request: Request):
        service, who = ctx(request, 'manage_tasks')
        with service.lock:
            try:
                service.referral_for(who, referral_id)
            except NotVisible:
                raise hidden(service, who, 'create_task', referral_id)
            tid, now = new_id('tsk'), service.clock()
            service.q('INSERT INTO tasks VALUES(?,?,?,?,?,?,?,?)', tid, referral_id, body.title, 'open', 1, who.user_id, now, now)
            service.db.commit()
            service.audit(who, 'create_task', referral_id, 'allowed')
            return {'taskId': tid, 'status': 'open', 'version': 1}

    @secured.patch('/referrals/{referral_id}/tasks/{task_id}')
    def patch_task(referral_id: str, task_id: str, body: TaskPatch, request: Request):
        service, who = ctx(request, 'manage_tasks')
        with service.lock:
            try:
                service.referral_for(who, referral_id)
            except NotVisible:
                raise hidden(service, who, 'update_task', referral_id)
            task = service.q('SELECT * FROM tasks WHERE task_id=? AND referral_id=?', task_id, referral_id).fetchone() \
                if ID_RE.match(task_id) else None
            if task is None:
                raise hidden(service, who, 'update_task', referral_id, 'task_not_found')
            if body.version != task['version']:
                service.audit(who, 'update_task', referral_id, 'denied', 'stale')
                raise HTTPException(409, 'This task changed. Reload the latest version.')
            service.q('UPDATE tasks SET status=?, version=version+1, updated_at=? WHERE task_id=?', body.status, service.clock(), task_id)
            service.db.commit()
            service.audit(who, 'update_task', referral_id, 'allowed')
            return {'taskId': task_id, 'status': body.status, 'version': task['version'] + 1}

    @secured.delete('/referrals/{referral_id}')
    def delete_referral(referral_id: str, request: Request):
        service, who = ctx(request, 'delete_referral')
        with service.lock:
            if not ID_RE.match(referral_id) or service.q('SELECT 1 FROM referrals WHERE referral_id=?', referral_id).fetchone() is None:
                raise hidden(service, who, 'delete_referral', referral_id)
            removed = service.delete_referral(referral_id)
            service.audit(who, 'delete_referral', referral_id, 'allowed', f'documents:{removed}')
            return {'deleted': True, 'documentsRemoved': removed}

    @secured.post('/purge-expired')
    def purge(request: Request):
        service, who = ctx(request, 'purge_expired')
        if not service.retention_days:
            raise HTTPException(409, 'No retention period is configured. IHH must decide one before anything is purged automatically.')
        ids = service.purge_expired()
        service.audit(who, 'purge_expired', None, 'allowed', f'count:{len(ids)}')
        return {'purged': len(ids)}

    @secured.post('/merge-proposals', status_code=201)
    def propose_merge(body: MergeIn, request: Request):
        service, who = ctx(request, 'propose_merge')
        with service.lock:
            a, b = body.fromPersonId, body.intoPersonId
            if a == b or not (ID_RE.match(a) and ID_RE.match(b)) or not (service.person_visible(who, a) and service.person_visible(who, b)):
                raise hidden(service, who, 'propose_merge', None, 'person_not_visible')
            pid = new_id('mrg')
            service.q('INSERT INTO merge_proposals VALUES(?,?,?,?,?,NULL,?,NULL)', pid, a, b, 'pending', who.user_id, service.clock())
            service.db.commit()
            service.audit(who, 'propose_merge', None, 'allowed')
            return {'proposalId': pid, 'state': 'pending', 'note': 'Nothing is merged until an administrator confirms.'}

    @secured.post('/merge-proposals/{proposal_id}/confirm')
    def confirm_merge(proposal_id: str, body: MergeConfirm, request: Request):
        service, who = ctx(request, 'confirm_merge')
        with service.lock:
            prop = service.q('SELECT * FROM merge_proposals WHERE proposal_id=?', proposal_id).fetchone() if ID_RE.match(proposal_id) else None
            if prop is None:
                raise hidden(service, who, 'confirm_merge', None, 'proposal_not_found')
            if prop['state'] != 'pending':
                raise HTTPException(409, 'This proposal was already decided.')
            if prop['proposed_by'] == who.user_id:
                service.audit(who, 'confirm_merge', None, 'denied', 'self_confirm')
                raise HTTPException(403, 'A different administrator must confirm a merge you proposed.')
            service.q('UPDATE persons SET merged_into=? WHERE person_id=?', prop['into_person_id'], prop['from_person_id'])
            service.q("UPDATE merge_proposals SET state='confirmed', decided_by=?, decided_at=? WHERE proposal_id=?",
                      who.user_id, service.clock(), proposal_id)
            service.db.commit()
            service.audit(who, 'confirm_merge', None, 'allowed')
            return {'proposalId': proposal_id, 'state': 'confirmed'}

    @secured.get('/audit')
    def read_audit(request: Request):
        service, who = ctx(request, 'read_audit')
        with service.lock:
            rows = service.q('SELECT at,actor_id,institution_id,role,action,referral_id,outcome,code FROM audit ORDER BY id DESC LIMIT 500').fetchall()
            return {'events': [dict(r) for r in rows],
                    'note': 'IDs and outcome codes only. Stored beside the records, so it is not tamper-proof.'}

    router.include_router(secured)
    return router


def service_from_env(env=None, provider: AuthProvider | None = None) -> SharedService | None:
    env = os.environ if env is None else env
    provider = provider or provider_from_env(env)
    folder = (env.get('IHH_SHARED_STORE_DIR') or '').strip()
    if not folder or not provider.status().ready:
        return None
    days = (env.get('IHH_RETENTION_DAYS') or '').strip()
    return SharedService(Path(folder), provider, int(days) if days.isdigit() and int(days) > 0 else None)
