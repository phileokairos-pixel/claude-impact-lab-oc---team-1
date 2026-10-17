# Local rehearsal script (BE-06)

Everything below runs from a clean checkout with no key and no model. A secret, if you later add one, goes in the environment (see `.env.example`), never in Git. Use **synthetic or event-permitted** PDFs only.

## Start
```bash
python3 -m venv .venv && . .venv/bin/activate
python3 -m pip install -r backend/requirements-dev.txt
npm --prefix frontend run build
python3 -m uvicorn backend.app:app --host 127.0.0.1 --port 8000
```
Open http://127.0.0.1:8000/ , choose a PDF, press **Extract text with local backend**, save a page note, record a next step.

## What works today
Upload, text/OCR with original page numbers and per-page flags, search, page notes, next-step confirmation, unsent draft. Server-side (API only, no UI yet): field review, allowed-action reasons, reviewed export, timing events and summary (see `docs/backend-review-contract.md`).

## What is mocked or missing
No model analysis runs unless an adapter is configured (`IHH_ANALYSIS_ADAPTER`), and that has never been exercised against a real model. Field review and export cannot be driven from the browser until FE-03. History and timing are in server memory and vanish on restart. No authentication. Approval and denial are disabled.

## Timing a rehearsal
```bash
curl -s -X POST localhost:8000/api/referrals/$ID/timing -H 'content-type: application/json' -d '{"event":"pause","reason":"coordinator-break"}'
curl -s -X POST localhost:8000/api/referrals/$ID/timing -H 'content-type: application/json' -d '{"event":"resume"}'
curl -s localhost:8000/api/referrals/$ID/timing
curl -s localhost:8000/api/timing/summary
```
Use `wait_start` / `wait_end` (reason `hospital` or `authorization`) for time spent waiting on others. Record the manual baseline for the same packet separately; a rehearsal on a synthetic packet says nothing about real time saved.

## Regression walkthrough
`python3 -m unittest discover -s backend/tests -v` includes the end-to-end test: upload → analysis (synthetic fake) → every cited page opens and contains its quote → page note → corrections → pause/resume → confirmation (repeat is idempotent) → unsent export → a later correction invalidates the confirmation, draft and export.
