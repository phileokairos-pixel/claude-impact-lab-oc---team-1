# BE-04 · P0 · Enforce human review and invalidate stale outcomes

Owner: backend teammate, with frontend coordination. Status: proposed. Depends on BE-03; guard tests can start with synthetic fixtures.

## Confirmed bug
`referral-review.html:233–247` unlocks approval after acknowledgement of flags even when a failed rule remains. The acceptance draft is unconditional. Unchecking a flag leaves an earlier acceptance draft visible. There is no explicit reviewer rationale or versioned decision record.

## Scope
- `PATCH /api/referrals/{id}/review` stores original value, corrected value/assessment, reviewer, reason, source, and version.
- Field corrections invalidate dependent findings and previous confirmed outcomes/drafts.
- `POST /api/referrals/{id}/outcome` validates the authoritative server state and captures rationale/attestation. Support clarification and clinical escalation as open workflow states.
- Generate an editable, unsent draft from the confirmed snapshot, not the original hardcoded findings.
- Preserve review history for the local demo; clearly distinguish a demo reviewer label from authenticated identity. Do not claim production clinical-audit readiness.

## Acceptance criteria
- Ticking “checked” does not resolve a failed, conflicting, or missing criterion. Approval stays unavailable with unresolved blockers or incomplete applicable-rule coverage.
- Denial requires a reviewed reason and an unmet applicable criterion; do not silently convert unknown into failure.
- Any later edit/uncheck invalidates the old confirmation and draft until reviewed again.
- Missing reviewer/rationale/attestation is rejected. Duplicate confirmation is idempotent; stale versions return 409.
- A response records actual confirmed findings; no unconditional acceptance template while blockers remain.
- No real outbound sending. Add regression tests for the reproduced checkbox/stale-draft bugs.

## Frontend handoff
Return review version, allowed next actions with reasons, invalidated finding IDs, and updated draft state. Clinical override policy is not established; default to escalation rather than inventing an override path.
