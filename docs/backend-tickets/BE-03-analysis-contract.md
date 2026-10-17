# BE-03 · P0 · Return validated form fields and rule findings

Owner: backend teammate. Status: proposed. Depends on BE-02. Frontend can use a synthetic contract fixture immediately.

## Problem
The current model output is JSON-parsed but not schema-validated; its object-based rules and `fails` status do not match the HTML's array-based rules and `fail` status. There is no form-prefill payload, coverage report, or result-loading adapter.

## Scope
- Agree one versioned schema with the frontend; follow the types in `docs/frontend-research-and-handoff.md`.
- `GET /api/referrals/{id}` returns document manifest, extracted form fields, rule findings, contradictions, clarification requests, coverage, authorization state, and review version.
- Use stable criteria IDs from `admission-criteria.json`; apply internal-document precedence. Questions and document requirements are not automatically exclusion rules.
- Keep original field extraction separate from human-confirmed values. Support missing, redacted, conflicting, and unreadable states.
- Every factual value/finding needs traceable page evidence; preserve contradictory values instead of choosing silently.
- Validate model schema, enums, known rule IDs, citation page bounds, and required coverage before marking a job ready. Treat document text as untrusted evidence, not instructions.

## Acceptance criteria
- A synthetic fixture loads in our frontend through a single adapter; no hand-written per-packet conditionals or HTML fragments.
- Malformed/truncated JSON, invented rule IDs, invalid page numbers, or missing required fields produce a visible validation error or bounded retry, never a fabricated result.
- Missing data never becomes “meets”; redacted dates cannot establish time-window compliance.
- Authorization request, authorization approval, and clinical eligibility are distinct.
- Coverage reports applicable/evaluated/unresolved rules. Partial evaluation cannot enable approval.
- No IHH evaluation labels enter prompts, retrieval, or live result payloads.

## Frontend handoff
Deliver a checked-in synthetic JSON fixture plus schema, status mapping, version, and errors. Keep real results ignored. The frontend must clearly show partial/failed jobs and unsupported fields.
