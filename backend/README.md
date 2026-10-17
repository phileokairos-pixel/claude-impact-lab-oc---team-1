# Local packet-processing backend

This implements the first adoption step: a permitted PDF becomes searchable text alongside its original pages, with explicit human review and an unsent clarification/escalation draft. It does not extract clinical form fields, apply admission criteria, call an AI provider, or make eligibility recommendations.

## Start

From the repository root, with Python 3.12+:

```bash
python3 -m venv .venv
. .venv/bin/activate
python3 -m pip install -r backend/requirements.txt
python3 -m uvicorn backend.app:app --host 127.0.0.1 --port 8000
```

Tesseract must be installed for image-only scans (`tesseract --version`). On Debian/Ubuntu its package is `tesseract-ocr`; install through your environment's approved system-package workflow. PyMuPDF renders PDFs, so Poppler is not needed by this service. Native PDF text works without Tesseract; scan pages explicitly fail OCR if it is unavailable. Direct Python dependency versions are pinned; transitive dependencies are not hash-locked.

Open the server root in your local browser. It serves the same frontend with an **Extract text with local backend** action after selecting a permitted PDF. The app detects this service only on localhost. It never uploads a PDF from GitHub Pages to an arbitrary remote server.

No API keys are needed. This is not a public backend deployment: bind only to localhost. Host and Origin guards reject nonlocal/cross-site requests. There is no production authentication, tenant isolation, durable clinical audit, or compliance certification.

## What is implemented

- Real PDF parsing and validation: extension/signature, corruption, password protection, 25 MB size and 60-page limits.
- One processing worker; up to four admitted active/queued jobs and twelve packets per session.
- Page rendering bounded to 2,000 pixels on the longest dimension (up to 3× source resolution).
- Native text extraction where available; Tesseract for pages with little/no native text, bounded to 40 seconds per page.
- Original PDF page numbers retained on every result, including failed pages. Page images remain reviewable when OCR fails.
- Page text is labeled unverified. `no_text_detected` never asserts that a page is blank or a fact is absent. Long text is capped at 100,000 characters per page and marked `truncated`.
- Packet-wide literal text search with original-page snippets (maximum twenty matches; explicit truncation). A failed search does not prove absence because OCR may miss text.
- Versioned page notes; stale writes rejected. Editing notes invalidates prior next-step confirmation and draft.
- Server-side rejection of approval/denial while clinical analysis is absent. Clarification/escalation requires a page review, rationale, reviewer label, and attestation.
- Editable unsent draft and local export. There is no email/fax sending.

## Endpoints

| Method / path | Result |
|---|---|
| GET `/health` | Capability flags, limits, ephemeral-storage description |
| POST `/api/referrals` (multipart `file`) | 202: referral ID, job ID, initial version |
| GET `/api/jobs/{id}` | Actual queued/rendering/extracting/text_ready/failed state and processed-page counts |
| GET `/api/referrals/{id}` | Original-page manifest/text, explicit disconnected analysis, reviews and current outcome |
| GET `/api/referrals/{id}/search?q=term` | Unverified text snippets with original page numbers |
| GET `/api/referrals/{id}/pages/{n}/image` | Rendered original page |
| PATCH `/api/referrals/{id}/review` | `{version, page, reviewer, note}` → revised record; invalidates prior outcome |
| POST `/api/referrals/{id}/outcome` | `{version, decision, reviewer, rationale, attested}` → guarded next step |
| GET `/api/referrals/{id}/draft` | Unsent draft only for the current confirmed version |

`text_ready` means text processing finished, **not** clinical analysis completed. `partial: true` indicates a page needs manual attention. An approval/denial attempt is always rejected in this version; no client-side override can enable it.

## Data handling and limits

PDFs and page images go in a unique restricted temporary directory outside the checkout; text and review records live in server memory. Graceful shutdown removes the directory. A hard kill can leave temporary files, so inspect and remove the corresponding `ihh-local-packets-*` directory when appropriate. Do not log OCR text or put packet artifacts into Git. Original filenames are not used as storage paths. No data is served by a generic directory mount.

Data is **not durable**. Browser refresh can lose its selected file/job ID; server restart clears all jobs and reviews. Repeating a confirmation using the old version is rejected (409); there is no full idempotency-key replay protocol. Coordinator initials are a local demo label, not authenticated identity. OCR orientation/skew correction, handwriting/checkbox accuracy, duplicate detection, and multi-form extraction remain outstanding.

## Test

```bash
python3 -m pip install -r backend/requirements-dev.txt
python3 -m unittest discover -s backend/tests -v
npm --prefix frontend test
```

API tests use synthetic documents and injected OCR for deterministic error coverage. Real Tesseract was separately exercised on a generated scanned-image PDF. The downloaded de-identified R01 packet also completed 34/34 pages with original numbers preserved; this checks pipeline execution, not OCR accuracy or clinical correctness. No patient-specific text is included in this repository.

The browser workflow was tested using the public blank referral form: actual PDF text/page images, review note, confirmation, unsent draft, invalidation after an edit, and mobile layout. The local flow test is `backend/tests/browser.cjs`, requiring Playwright/Chromium and a running server; set `PLAYWRIGHT_MODULE` when using an externally installed module.

## Handoff to Harjeev and Vibhu

- BE-01: local API slice works; public authenticated hosting, production robustness, and AI jobs remain separate work.
- BE-02: rendering/OCR/page provenance/search work; orientation, quality assessment, structured checkbox/handwriting extraction and source regions still need attention.
- BE-03: no model or clinical extractor is connected. Implement versioned fields/findings with real evidence; do not promote OCR text into verified facts.
- BE-04: local next-step guards and stale-draft invalidation work. Complete rule-dependent invalidation, authenticated reviewers, durable audit and idempotency remain.

See `docs/adoption-and-demo-strategy.md` for the staged adoption plan. Keep existing synthetic demo and real-text workflow clearly separated.
