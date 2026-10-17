# BE-01 · P0 · Add a runnable local PDF analysis API

Owner: backend teammate. Status: proposed. Blocks: real frontend upload-to-analysis.

## Problem
The archive has a static page and a CLI evaluator, not a backend the frontend can call. `blind_eval.py` creates the API client and loads criteria at import time, so even scoring depends on inference setup.

## Scope
- Add a small local service (FastAPI is a reasonable default, but reuse the team's chosen stack).
- `POST /api/referrals`: validate and store a permitted PDF outside the public web root; return HTTP 202 with `referralId`, `jobId`, and `version`.
- `GET /api/jobs/{jobId}`: return actual `queued`, `rendering`, `extracting`, `checking`, `needs_review`, or `failed` state with useful errors.
- Add `/health`, documented start command, pinned dependencies, and a non-secret `.env.example`.
- Make criteria paths explicit; use `challenges/1-referral-intake/criteria/` in this repo. Instantiate model client only for inference. Configure and verify an accessible model ID rather than assuming the shipped default works.
- Keep keys server-side. Do not add secret values, OCR text, PDFs, or results to Git.

## Acceptance criteria
- Fresh documented startup succeeds; `/health` works without invoking the model.
- One supported PDF produces a job ID; invalid, empty, corrupt, encrypted, and oversized inputs produce clear errors rather than success.
- Missing API configuration is reported clearly; score-only execution needs no API key.
- Model errors/timeouts surface as failed jobs; the frontend never receives an invented successful analysis.
- Packet/result identifiers are opaque; file-path traversal is rejected; documents are not exposed through a public static directory.

## Frontend handoff
Provide base URL, upload field name, exact response/error JSON, polling interval, and file/page limits. Start same-origin or a narrowly configured local CORS origin. No production deployment is required for this ticket.
