# Shared records and access boundaries (LOOP-06, issue #27)

**Status: readiness code and tests with synthetic data. Not a deployed or production-secure service.** Nothing here authorizes a live patient-data rollout. The public Pages demo stays synthetic and browser-only. The local OCR/review flow in `backend/app.py` is unchanged and still unauthenticated on localhost.

## What was built (functional, tested)
`backend/access.py` (identity and policy) and `backend/shared.py` (SQLite store, document storage, routes under `/api/shared`), mounted by a few lines in `create_app`. 26 tests in `backend/tests/test_shared.py`, each mutation-checked.

- **Default deny.** Shared routes answer 503 unless an auth mode is ready *and* `IHH_SHARED_STORE_DIR` is set. In the default `local-prototype` mode they stay off, because shared records without identity is what this ticket forbids.
- **Server-side identity.** The bearer token is the only identity source. A role in a body or header, or the UI role switch, is ignored (extra body fields are rejected). Authentication runs before body validation, so unauthenticated callers learn nothing about schemas.
- **Roles and scope.** `hospital-staff` see only referrals from their own institution. `ihh-staff` see only referrals an `ihh-admin` explicitly assigned to them. `ihh-admin` see all. `client` sees only an allowlisted summary of their own referrals. Not-visible records answer 404, not 403, so existence does not leak.
- **Three data layers.** `shared` (hospital + IHH), `internal` (IHH only: internal notes, assignments, tasks, internal documents) and a separately authored **client summary** (exactly four keys, written by IHH staff; nothing is copied from the other layers).
- **Stable linked IDs.** `personId` → `referralId` → `documentId` (versioned by `groupId`) → `taskId`. Writes need the current `version` (409 when stale).
- **Person merge needs human confirmation.** A proposal changes nothing; a *different* administrator must confirm with an explicit `confirm: true`. Referrals then resolve to the surviving person; the old ID stays linked.
- **Documents.** PDF only, 25 MB, stored under a 0700 directory with 0600 files, served only through an authorized route as an attachment (original filename never stored or returned), never statically.
- **Audit.** Every allowed and denied action records actor, institution, role, action, referral ID and an outcome code. No note text, file names or tokens. Admin-only to read.
- **Deletion, retention, backup.** Admin hard-delete removes rows and document bytes (audit keeps IDs only). Automatic purge of *closed* referrals exists but is disabled until `IHH_RETENTION_DAYS` is set. `SharedService.backup(dest)` copies the database (SQLite backup API) and documents; tests prove restart and restore recovery, including that scoping survives.
- **No sensitive values in logs or build output.** Tested with sentinel strings; `.gitignore` covers store, SQLite, WAL, dev users file and backups, checked by `test_repo_hygiene`.

## Permissions (action → roles that may ever perform it; record-level checks still apply)
| Action | ihh-admin | ihh-staff | hospital-staff | client |
|---|---|---|---|---|
| create person / referral, list, view, upload and download documents | all | assigned only | own institution only | no |
| view or edit internal layer | yes | assigned only | no | no |
| export (JSON, unsent) | yes | assigned only | no | no |
| tasks | yes | assigned only | no | no |
| assign staff, delete, purge, confirm merge, read audit | yes | no | no | no |
| client summary | no | no | no | own only |

## Rehearse locally (dev-sessions; not production authentication)
Create a users file **outside the repo** and give out tokens separately:
```bash
python3 - <<'PY'
import hashlib, json, secrets
users = [("admin1","ihh","ihh-admin"),("staff1","ihh","ihh-staff"),("hospA","hospital-a","hospital-staff")]
out = []
for uid, inst, role in users:
    token = secrets.token_urlsafe(24); print(uid, token)
    out.append({"userId": uid, "institutionId": inst, "role": role, "tokenSha256": hashlib.sha256(token.encode()).hexdigest()})
json.dump({"users": out}, open("../dev-users.json", "w"))
PY
IHH_AUTH_MODE=dev-sessions IHH_DEV_USERS_FILE=../dev-users.json IHH_SHARED_STORE_DIR=../shared-store \
  python3 -m uvicorn backend.app:app --host 127.0.0.1 --port 8000
curl -s localhost:8000/api/shared/status
curl -s -H "Authorization: Bearer <token>" localhost:8000/api/shared/me
```
Dev sessions have no expiry, rotation, MFA or revocation. Client users additionally need a `personId`.

## Decisions IHH must make (blocked, not simulated)
1. **Identity provider** and how staff, hospital and client accounts are provisioned and removed. `IHH_AUTH_MODE=oidc` reports `blocked: identity_provider_decision`.
2. **Access policy:** may IHH staff see unassigned referrals? How are hospital users tied to institutions? Who may share across institutions? The code takes the strictest option (explicit assignment, own institution).
3. **Retention and deletion:** how long closed referrals and documents are kept, whether deletion is hard or soft, and legal hold. Nothing is purged automatically until a period is set.
4. **Hosting and key management:** where this runs, who operates it, how secrets and backups are stored, encryption at rest (not implemented; SQLite and document files are plaintext on disk).
5. **Backup destination and recovery objectives.** `backup()` only copies locally and is not scheduled.
6. **What a person receiving care may see**, and by what verified link a login maps to a `personId`.

## Not done / known limits
- No production login, session expiry, rate limiting or lockout; tokens compare by hash but dev tokens are long-lived.
- No encryption at rest, no tamper-evident audit (the audit table sits beside the data and an administrator of the host can alter it).
- Single process and single SQLite file: no multi-node safety, no point-in-time recovery, no scheduled backup.
- Person merge matching is manual only; there is no duplicate detection.
- Not wired to the existing local review flow (`/api/referrals/...`), to the frontend, or to onboarding persistence from LOOP-01 (#22). Coordinate with Aaron for client-safe consumption once the contract is agreed.
- No notifications, CRM writes or real patient data, by design.
