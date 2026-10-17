# BE-05 · P0 before accuracy claims · Make evaluation blind and reproducible

Owner: backend teammate. Status: proposed. Depends on BE-03.

## Problem
The static page embeds actual IHH decisions and admits its suggestions were written after those labels were opened. Its agreement is not blind-test evidence. The separate `suggest` function avoids reading labels, but caching only by filename can silently reuse outputs after inputs or criteria change.

## Scope
- Keep the suggestion and scoring steps separate; keep labels out of the app and model context.
- Store run metadata: packet hash, criteria hash/version, prompt version, model ID, timestamp, analysis schema version, and status.
- Cache by those inputs or require an explicit run ID; never silently reuse stale suggestions.
- Validate outputs before scoring; report expected, attempted, completed, failed, missing, hold, and unmatched cases.
- Run scoring without importing/constructing an API client or requiring network access.

## Acceptance criteria
- Synthetic test proves generation does not open the evaluation labels.
- Changing criteria or packet text cannot silently reuse old output.
- Zero completed cases produces “no evaluated results,” not a success claim; missing/failed cases remain visible in the denominator accounting.
- Keep holds separate from approvals/denials; report disagreement for human review without claiming the historical reasons are known.
- Matching labels alone does not establish citation or clinical correctness. Include a reviewer check of key source claims.
- No accuracy claim based on the static HTML examples. Add a fresh unseen/held-out packet where available.

## Frontend handoff
Offline evaluation summary only; do not return actual historical outcomes in the live review response. Never use model agreement as a live eligibility score.
