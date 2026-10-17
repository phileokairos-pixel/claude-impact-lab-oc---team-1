"""LOOP-06: authentication boundary, institution scoping, client-safe summary, documents, audit,
deletion, retention, restart and backup. SYNTHETIC only; dev-session tokens are test constants.

These tests prove server-side authorization over invented records. They do not prove production
security: there is no real identity provider, hosting, key management or deployed backup."""
import json
import logging
import os
import shutil
import stat
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi.testclient import TestClient

from backend.access import DevSessions, hash_token, provider_from_env
from backend.analysis import AnalysisRuntime
from backend.app import create_app
from backend.shared import SharedService, now_iso

PDF = b'%PDF-1.4\n% synthetic test document\n%%EOF\n'
SECRET = 'SENTINEL-INTERNAL-NOTE-7731'
NOTE = 'SENTINEL-SHARED-NOTE-4419'

USERS = [
    {'userId': 'admin1', 'institutionId': 'ihh', 'role': 'ihh-admin', 'token': 'tok-admin1'},
    {'userId': 'admin2', 'institutionId': 'ihh', 'role': 'ihh-admin', 'token': 'tok-admin2'},
    {'userId': 'staff1', 'institutionId': 'ihh', 'role': 'ihh-staff', 'token': 'tok-staff1'},
    {'userId': 'staff2', 'institutionId': 'ihh', 'role': 'ihh-staff', 'token': 'tok-staff2'},
    {'userId': 'hospA', 'institutionId': 'hospital-a', 'role': 'hospital-staff', 'token': 'tok-hospA'},
    {'userId': 'hospB', 'institutionId': 'hospital-b', 'role': 'hospital-staff', 'token': 'tok-hospB'},
    {'userId': 'clientX', 'institutionId': 'clients', 'role': 'client', 'token': 'tok-clientX', 'personId': 'per_client_x'},
    {'userId': 'clientY', 'institutionId': 'clients', 'role': 'client', 'token': 'tok-clientY', 'personId': 'per_client_y'},
]


def provider():
    return DevSessions([{**{k: v for k, v in u.items() if k != 'token'}, 'tokenSha256': hash_token(u['token'])} for u in USERS])


def auth(user):
    return {'Authorization': 'Bearer tok-' + user}


class Base(unittest.TestCase):
    clock_value = None

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.open_service(self.tmp / 'store')
        for pid, inst in (('per_client_x', 'hospital-a'), ('per_client_y', 'hospital-b')):
            self.svc.q('INSERT INTO persons VALUES(?,?,?,NULL,?,?)', pid, inst, 'synthetic', 'seed', now_iso())
        self.svc.db.commit()

    def open_service(self, folder, **kw):
        self.svc = SharedService(folder, provider(), clock=lambda: (self.clock_value or now_iso()), **kw)
        self.addCleanup(lambda: self.svc.db and None)
        self.client = TestClient(create_app(ocr=lambda i: '', analysis=AnalysisRuntime(env={}), auth=provider(), shared=self.svc))
        self.client.__enter__()
        self.addCleanup(self.client.__exit__, None, None, None)

    def call(self, method, path, user=None, **kw):
        headers = {**(auth(user) if user else {}), **kw.pop('headers', {})}
        return self.client.request(method, '/api/shared' + path, headers=headers, **kw)

    def make_referral(self, user='hospA', person=None, title='Synthetic referral'):
        if person is None:
            person = self.call('POST', '/persons', user, json={'label': 'Synthetic Person A'}).json()['personId']
        r = self.call('POST', '/referrals', user, json={'personId': person, 'title': title, 'sharedNote': NOTE,
                                                        **({'sourceInstitutionId': 'hospital-a'} if user.startswith(('staff', 'admin')) else {})})
        self.assertEqual(r.status_code, 201, r.text)
        return r.json()

    def staff_sets_internal(self, rid, user='admin1'):
        v = self.call('GET', f'/referrals/{rid}', user).json()['version']
        r = self.call('PATCH', f'/referrals/{rid}', user, json={'version': v, 'internalNote': SECRET, 'status': 'in-review',
                                                                'clientStatusLabel': 'Someone is reviewing it',
                                                                'clientNextStep': 'We will contact you.'})
        self.assertEqual(r.status_code, 200, r.text)


class ModeTests(unittest.TestCase):
    def test_default_mode_keeps_shared_records_off(self):
        with TestClient(create_app(ocr=lambda i: '', analysis=AnalysisRuntime(env={}))) as c:
            s = c.get('/api/shared/status').json()
            self.assertEqual((s['ready'], s['blockedBy'], s['productionReady']), (False, 'authentication_not_configured', False))
            self.assertEqual(c.get('/api/shared/referrals', headers=auth('admin1')).status_code, 503)
            self.assertEqual(c.get('/health').status_code, 200)

    def test_oidc_is_blocked_not_simulated(self):
        p = provider_from_env({'IHH_AUTH_MODE': 'oidc'})
        with TestClient(create_app(ocr=lambda i: '', analysis=AnalysisRuntime(env={}), auth=p)) as c:
            s = c.get('/api/shared/status').json()
            self.assertEqual((s['ready'], s['blockedBy']), (False, 'identity_provider_decision'))
            self.assertEqual(c.get('/api/shared/referrals', headers=auth('admin1')).status_code, 503)

    def test_dev_sessions_without_a_store_is_not_ready(self):
        with TestClient(create_app(ocr=lambda i: '', analysis=AnalysisRuntime(env={}), auth=provider())) as c:
            self.assertEqual(c.get('/api/shared/status').json()['blockedBy'], 'shared_store_not_configured')

    def test_dev_user_file_validation(self):
        bad = DevSessions([{'userId': 'a', 'institutionId': 'hospital-a', 'role': 'ihh-admin', 'tokenSha256': hash_token('x')},
                           {'userId': 'b', 'institutionId': 'ihh', 'role': 'client', 'tokenSha256': hash_token('y')},
                           {'userId': 'c', 'institutionId': 'ihh', 'role': 'ihh-staff', 'tokenSha256': 'plaintext-token'},
                           {'userId': 'd', 'institutionId': 'ihh', 'role': 'root', 'tokenSha256': hash_token('z')}])
        self.assertEqual(bad.by_hash, {})
        self.assertFalse(bad.status().ready)


class AccessTests(Base):
    def test_every_route_needs_a_valid_session(self):
        ref = self.make_referral()['referralId']
        routes = [('GET', '/me'), ('GET', '/referrals'), ('GET', f'/referrals/{ref}'), ('GET', f'/referrals/{ref}/export'),
                  ('GET', f'/referrals/{ref}/client-summary'), ('GET', '/audit'), ('DELETE', f'/referrals/{ref}'),
                  ('POST', f'/referrals/{ref}/assign')]
        for headers in ({}, {'Authorization': 'Bearer nope'}, {'Authorization': 'Basic abc'}, {'Authorization': 'Bearer '},
                        {'X-Role': 'ihh-admin', 'X-User': 'admin1'}):
            for method, path in routes:
                with self.subTest(path=path, headers=list(headers)):
                    self.assertEqual(self.call(method, path, headers=headers, **({'json': {}} if method == 'POST' else {})).status_code, 401)

    def test_identity_comes_from_the_token_never_from_the_request(self):
        r = self.call('POST', '/persons', 'hospA', json={'label': 'x', 'role': 'ihh-admin'})
        self.assertEqual(r.status_code, 422)                   # extra fields are refused
        r = self.call('GET', '/audit', 'hospA', headers={'X-Role': 'ihh-admin'})
        self.assertEqual(r.status_code, 403)
        self.assertEqual(self.call('GET', '/me', 'hospA').json()['role'], 'hospital-staff')

    def test_hospital_scoping_across_institutions(self):
        ref = self.make_referral('hospA')
        rid = ref['referralId']
        self.assertEqual([r['referralId'] for r in self.call('GET', '/referrals', 'hospA').json()['referrals']], [rid])
        self.assertEqual(self.call('GET', '/referrals', 'hospB').json()['referrals'], [])
        v = ref['version']
        for method, path, kw in (('GET', f'/referrals/{rid}', {}), ('PATCH', f'/referrals/{rid}', {'json': {'version': v, 'title': 'x'}}),
                                 ('GET', f'/referrals/{rid}/export', {}), ('POST', f'/referrals/{rid}/tasks', {'json': {'title': 'x'}}),
                                 ('GET', f'/referrals/{rid}/client-summary', {})):
            r = self.call(method, path, 'hospB', **kw)
            self.assertIn(r.status_code, (403, 404), path)
        self.assertEqual(self.call('GET', f'/referrals/{rid}', 'hospB').status_code, 404, 'no existence leak')
        self.assertEqual(self.call('GET', f'/referrals/ref_doesnotexist', 'hospB').status_code, 404)
        self.assertEqual(self.call('GET', f'/referrals/{rid}', 'hospA').status_code, 200)

    def test_hospital_staff_cannot_create_for_another_institution_or_use_foreign_persons(self):
        other = self.call('POST', '/persons', 'hospB', json={'label': 'B person'}).json()['personId']
        r = self.call('POST', '/referrals', 'hospA', json={'personId': other, 'title': 't'})
        self.assertEqual(r.status_code, 404)
        mine = self.call('POST', '/persons', 'hospA', json={'label': 'A person'}).json()['personId']
        r = self.call('POST', '/referrals', 'hospA', json={'personId': mine, 'title': 't', 'sourceInstitutionId': 'hospital-b'})
        self.assertEqual(r.status_code, 403)

    def test_ihh_staff_need_explicit_assignment_and_only_admins_assign(self):
        rid = self.make_referral('hospA')['referralId']
        self.assertEqual(self.call('GET', f'/referrals/{rid}', 'staff1').status_code, 404)
        self.assertEqual(self.call('GET', '/referrals', 'staff1').json()['referrals'], [])
        v = self.call('GET', f'/referrals/{rid}', 'admin1').json()['version']
        self.assertEqual(self.call('POST', f'/referrals/{rid}/assign', 'staff1', json={'version': v, 'staff': ['staff1']}).status_code, 403)
        self.assertEqual(self.call('POST', f'/referrals/{rid}/assign', 'admin1', json={'version': v, 'staff': ['staff1']}).status_code, 200)
        self.assertEqual(self.call('GET', f'/referrals/{rid}', 'staff1').status_code, 200)
        self.assertEqual(self.call('GET', f'/referrals/{rid}', 'staff2').status_code, 404)
        self.assertEqual(self.call('GET', f'/referrals/{rid}/export', 'staff2').status_code, 404)
        self.assertEqual(self.call('GET', f'/referrals/{rid}/export', 'staff1').status_code, 200)

    def test_unauthorized_exports_are_rejected(self):
        rid = self.make_referral('hospA')['referralId']
        self.assertEqual(self.call('GET', f'/referrals/{rid}/export', 'hospA').status_code, 403)   # sees it, may not export
        self.assertEqual(self.call('GET', f'/referrals/{rid}/export', 'clientX').status_code, 403)
        export = self.call('GET', f'/referrals/{rid}/export', 'admin1').json()
        self.assertFalse(export['sent'])


class DataLayerTests(Base):
    def test_internal_notes_never_reach_hospitals_or_clients_or_logs(self):
        ref = self.make_referral('hospA', person='per_client_x')
        rid = ref['referralId']
        self.staff_sets_internal(rid)
        hospital = self.call('GET', f'/referrals/{rid}', 'hospA')
        self.assertNotIn(SECRET, hospital.text)
        for key in ('internalNote', 'assignedStaff', 'clientSummary', 'tasks'):
            self.assertNotIn(key, hospital.json())
        self.assertIn(SECRET, self.call('GET', f'/referrals/{rid}', 'admin1').text)
        summary = self.call('GET', f'/referrals/{rid}/client-summary', 'clientX')
        self.assertEqual(summary.status_code, 200)
        self.assertEqual(set(summary.json()), {'referralId', 'statusLabel', 'nextStep', 'updatedAt'})
        self.assertNotIn(SECRET, summary.text)
        self.assertNotIn(NOTE, summary.text)
        self.assertEqual(self.call('GET', f'/referrals/{rid}/client-summary', 'clientY').status_code, 404)
        audit = self.call('GET', '/audit', 'admin1').text
        self.assertNotIn(SECRET, audit)
        self.assertNotIn(NOTE, audit)

    def test_nothing_sensitive_is_logged(self):
        with self.assertLogs(level=logging.DEBUG) as logs:
            logging.getLogger('probe').debug('start')
            rid = self.make_referral('hospA')['referralId']
            self.staff_sets_internal(rid)
            self.call('GET', f'/referrals/{rid}', 'hospB')
        joined = '\n'.join(logs.output)
        for needle in (SECRET, NOTE, 'tok-admin1', 'tok-hospA'):
            self.assertNotIn(needle, joined)

    def test_clients_cannot_use_staff_routes(self):
        rid = self.make_referral('hospA', person='per_client_x')['referralId']
        for method, path in (('GET', '/referrals'), ('GET', f'/referrals/{rid}'), ('GET', f'/referrals/{rid}/documents/doc_x'),
                             ('GET', '/audit')):
            self.assertEqual(self.call(method, path, 'clientX').status_code, 403, path)

    def test_role_limited_fields(self):
        rid = self.make_referral('hospA')['referralId']
        v = self.call('GET', f'/referrals/{rid}', 'hospA').json()['version']
        for body in ({'status': 'closed'}, {'internalNote': 'x'}, {'clientNextStep': 'x'}):
            r = self.call('PATCH', f'/referrals/{rid}', 'hospA', json={'version': v, **body})
            self.assertEqual(r.status_code, 403, body)
        self.assertEqual(self.call('PATCH', f'/referrals/{rid}', 'hospA', json={'version': v, 'bogus': 1}).status_code, 422)
        self.assertEqual(self.call('PATCH', f'/referrals/{rid}', 'hospA', json={'version': v, 'title': 'Updated'}).status_code, 200)

    def test_stale_writes_are_rejected(self):
        rid = self.make_referral('hospA')['referralId']
        v = self.call('GET', f'/referrals/{rid}', 'hospA').json()['version']
        self.assertEqual(self.call('PATCH', f'/referrals/{rid}', 'hospA', json={'version': v, 'title': 'First'}).status_code, 200)
        r = self.call('PATCH', f'/referrals/{rid}', 'hospA', json={'version': v, 'title': 'Second'})
        self.assertEqual(r.status_code, 409)
        self.assertEqual(self.call('GET', f'/referrals/{rid}', 'hospA').json()['title'], 'First')
        self.assertEqual(self.call('POST', f'/referrals/{rid}/assign', 'admin1', json={'version': v, 'staff': ['staff1']}).status_code, 409)
        task = self.call('POST', f'/referrals/{rid}/tasks', 'admin1', json={'title': 'Check bed'}).json()
        self.assertEqual(self.call('PATCH', f'/referrals/{rid}/tasks/{task["taskId"]}', 'admin1', json={'version': 1, 'status': 'done'}).status_code, 200)
        self.assertEqual(self.call('PATCH', f'/referrals/{rid}/tasks/{task["taskId"]}', 'admin1', json={'version': 1, 'status': 'blocked'}).status_code, 409)

    def test_stable_ids_link_person_referral_documents_and_tasks(self):
        person = self.call('POST', '/persons', 'hospA', json={'label': 'Synthetic'}).json()['personId']
        rid = self.make_referral('hospA', person=person)['referralId']
        doc = self.call('POST', f'/referrals/{rid}/documents', 'hospA', files={'file': ('a.pdf', PDF, 'application/pdf')}).json()
        task = self.call('POST', f'/referrals/{rid}/tasks', 'admin1', json={'title': 'Onboarding'}).json()
        view = self.call('GET', f'/referrals/{rid}', 'admin1').json()
        self.assertEqual(view['personId'], person)
        self.assertEqual([d['documentId'] for d in view['documents']], [doc['documentId']])
        self.assertEqual([t['taskId'] for t in view['tasks']], [task['taskId']])


class DocumentTests(Base):
    def upload(self, user, rid, **kw):
        form = {k: v for k, v in kw.items()}
        return self.call('POST', f'/referrals/{rid}/documents', user, files={'file': ('real-name.pdf', PDF, 'application/pdf')}, data=form)

    def test_cross_organization_document_access_is_denied(self):
        rid = self.make_referral('hospA')['referralId']
        doc = self.upload('hospA', rid).json()
        path = f'/referrals/{rid}/documents/{doc["documentId"]}'
        self.assertEqual(self.call('GET', path, 'hospA').content, PDF)
        self.assertEqual(self.call('GET', path, 'hospB').status_code, 404)
        self.assertEqual(self.call('GET', path, 'staff1').status_code, 404)          # unassigned
        self.assertEqual(self.call('GET', path).status_code, 401)
        other = self.make_referral('hospB')['referralId']
        self.assertEqual(self.call('GET', f'/referrals/{other}/documents/{doc["documentId"]}', 'hospB').status_code, 404,
                         'a document ID cannot be fetched through a different referral')
        r = self.call('GET', path, 'admin1')
        self.assertEqual((r.headers['content-type'], r.headers['cache-control']), ('application/pdf', 'no-store'))
        self.assertNotIn('real-name', r.headers['content-disposition'])

    def test_internal_documents_are_staff_only(self):
        rid = self.make_referral('hospA')['referralId']
        self.assertEqual(self.upload('hospA', rid, visibility='internal').status_code, 403)
        doc = self.upload('admin1', rid, visibility='internal').json()
        hospital_view = self.call('GET', f'/referrals/{rid}', 'hospA').json()
        self.assertEqual(hospital_view['documents'], [])
        self.assertEqual(self.call('GET', f'/referrals/{rid}/documents/{doc["documentId"]}', 'hospA').status_code, 404)
        self.assertEqual(self.upload('hospA', rid, supersedes=doc['documentId']).status_code, 404)

    def test_validation_and_versioning(self):
        rid = self.make_referral('hospA')['referralId']
        bad = self.call('POST', f'/referrals/{rid}/documents', 'hospA', files={'file': ('a.pdf', b'MZ not a pdf', 'application/pdf')})
        self.assertEqual(bad.status_code, 422)
        first = self.upload('hospA', rid).json()
        second = self.upload('hospA', rid, supersedes=first['documentId']).json()
        self.assertEqual((first['version'], second['version'], first['groupId'] == second['groupId']), (1, 2, True))
        self.assertEqual(self.call('GET', f'/referrals/{rid}/documents/{first["documentId"]}', 'hospA').status_code, 200,
                         'older versions stay available')

    def test_stored_files_are_private_and_not_served_statically(self):
        rid = self.make_referral('hospA')['referralId']
        doc = self.upload('hospA', rid).json()
        stored = self.svc.docs / f'{doc["documentId"]}.bin'
        self.assertEqual(stat.S_IMODE(stored.stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(self.svc.docs.stat().st_mode), 0o700)
        for url in (f'/{doc["documentId"]}.bin', f'/documents/{doc["documentId"]}.bin', '/shared.sqlite3'):
            self.assertEqual(self.client.get(url).status_code, 404)


class LifecycleTests(Base):
    def test_merge_needs_human_confirmation_by_a_second_administrator(self):
        a = self.call('POST', '/persons', 'admin1', json={'label': 'Synthetic A'}).json()['personId']
        b = self.call('POST', '/persons', 'admin1', json={'label': 'Synthetic A (duplicate)'}).json()['personId']
        rid = self.make_referral('admin1', person=a)['referralId']
        prop = self.call('POST', '/merge-proposals', 'admin1', json={'fromPersonId': a, 'intoPersonId': b}).json()
        self.assertEqual(self.call('GET', f'/referrals/{rid}', 'admin1').json()['personId'], a, 'a proposal changes nothing')
        pid = prop['proposalId']
        self.assertEqual(self.call('POST', f'/merge-proposals/{pid}/confirm', 'admin1', json={}).status_code, 422)
        self.assertEqual(self.call('POST', f'/merge-proposals/{pid}/confirm', 'admin1', json={'confirm': False}).status_code, 422)
        self.assertEqual(self.call('POST', f'/merge-proposals/{pid}/confirm', 'staff1', json={'confirm': True}).status_code, 403)
        self.assertEqual(self.call('POST', f'/merge-proposals/{pid}/confirm', 'admin1', json={'confirm': True}).status_code, 403,
                         'the proposer cannot confirm their own proposal')
        self.assertEqual(self.call('POST', f'/merge-proposals/{pid}/confirm', 'admin2', json={'confirm': True}).status_code, 200)
        self.assertEqual(self.call('GET', f'/referrals/{rid}', 'admin1').json()['personId'], b)
        self.assertEqual(self.call('POST', f'/merge-proposals/{pid}/confirm', 'admin2', json={'confirm': True}).status_code, 409)

    def test_merge_cannot_cross_institutions_for_non_admins(self):
        a = self.call('POST', '/persons', 'hospA', json={'label': 'A'}).json()['personId']
        b = self.call('POST', '/persons', 'hospB', json={'label': 'B'}).json()['personId']
        self.assertEqual(self.call('POST', '/merge-proposals', 'hospA', json={'fromPersonId': a, 'intoPersonId': b}).status_code, 403)
        self.assertEqual(self.call('POST', '/merge-proposals', 'staff1', json={'fromPersonId': a, 'intoPersonId': b}).status_code, 404)

    def test_deletion_removes_rows_and_document_bytes_but_keeps_an_id_only_audit(self):
        rid = self.make_referral('hospA')['referralId']
        doc = self.call('POST', f'/referrals/{rid}/documents', 'hospA', files={'file': ('a.pdf', PDF, 'application/pdf')}).json()
        stored = self.svc.docs / f'{doc["documentId"]}.bin'
        self.assertTrue(stored.exists())
        for user in ('hospA', 'staff1', 'clientX'):
            self.assertEqual(self.call('DELETE', f'/referrals/{rid}', user).status_code, 403)
        self.assertEqual(self.call('DELETE', f'/referrals/{rid}', 'admin1').json(), {'deleted': True, 'documentsRemoved': 1})
        self.assertFalse(stored.exists())
        self.assertEqual(self.call('GET', f'/referrals/{rid}', 'admin1').status_code, 404)
        self.assertEqual(self.call('GET', f'/referrals/{rid}/documents/{doc["documentId"]}', 'hospA').status_code, 404)
        events = self.call('GET', '/audit', 'admin1').json()['events']
        self.assertTrue(any(e['action'] == 'delete_referral' and e['referral_id'] == rid for e in events))
        self.assertNotIn(NOTE, json.dumps(events))
        self.assertEqual(self.svc.q('SELECT COUNT(*) AS n FROM documents').fetchone()['n'], 0)

    def test_retention_is_off_until_ihh_sets_it_then_purges_only_old_closed_referrals(self):
        old = self.make_referral('hospA')['referralId']
        self.assertEqual(self.call('POST', '/purge-expired', 'admin1').status_code, 409)
        self.svc.retention_days = 30
        for rid, status in ((old, 'closed'),):
            v = self.call('GET', f'/referrals/{rid}', 'admin1').json()['version']
            self.call('PATCH', f'/referrals/{rid}', 'admin1', json={'version': v, 'status': status})
        open_ref = self.make_referral('hospA')['referralId']
        self.clock_value = (datetime.now(timezone.utc) + timedelta(days=45)).isoformat(timespec='seconds')
        self.assertEqual(self.call('POST', '/purge-expired', 'hospA').status_code, 403)
        self.assertEqual(self.call('POST', '/purge-expired', 'admin1').json(), {'purged': 1})
        self.assertEqual(self.call('GET', f'/referrals/{old}', 'admin1').status_code, 404)
        self.assertEqual(self.call('GET', f'/referrals/{open_ref}', 'admin1').status_code, 200)

    def test_restart_and_backup_restore_recover_records_and_documents(self):
        person = self.call('POST', '/persons', 'hospA', json={'label': 'Synthetic'}).json()['personId']
        rid = self.make_referral('hospA', person=person)['referralId']
        doc = self.call('POST', f'/referrals/{rid}/documents', 'hospA', files={'file': ('a.pdf', PDF, 'application/pdf')}).json()
        self.staff_sets_internal(rid)
        backup = self.tmp / 'backup'
        self.svc.backup(backup)
        with self.assertRaises(FileExistsError):
            self.svc.backup(backup)
        self.client.__exit__(None, None, None)
        self.svc.close()
        for folder in (self.tmp / 'store', backup):                    # restart in place, and restore from backup
            self.open_service(folder)
            got = self.call('GET', f'/referrals/{rid}', 'admin1').json()
            self.assertEqual((got['personId'], got['internalNote']), (person, SECRET), folder.name)
            self.assertEqual(self.call('GET', f'/referrals/{rid}/documents/{doc["documentId"]}', 'hospA').content, PDF)
            self.assertEqual(self.call('GET', f'/referrals/{rid}', 'hospB').status_code, 404, 'scoping survives restart')
            self.client.__exit__(None, None, None)
            self.svc.close()
        self.open_service(self.tmp / 'store')                          # leave a live client for the cleanup hook

    def test_audit_is_admin_only_and_records_denials_without_content(self):
        rid = self.make_referral('hospA')['referralId']
        self.call('GET', f'/referrals/{rid}', 'hospB')
        self.call('GET', f'/referrals/{rid}/export', 'hospA')
        self.call('GET', '/referrals', headers={'Authorization': 'Bearer wrong'})
        self.assertEqual(self.call('GET', '/audit', 'hospA').status_code, 403)
        events = self.call('GET', '/audit', 'admin1').json()['events']
        outcomes = {(e['actor_id'], e['action'], e['outcome'], e['code']) for e in events}
        self.assertIn(('hospB', 'view_referral', 'denied', 'not_visible'), outcomes)
        self.assertIn(('hospA', 'export', 'denied', 'role'), outcomes)
        self.assertIn(('anonymous', 'request', 'denied', 'unauthenticated'), outcomes)
        self.assertNotIn(NOTE, json.dumps(events))


if __name__ == '__main__':
    unittest.main()
