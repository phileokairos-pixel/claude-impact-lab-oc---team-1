# Intake — frontend prototype

A dependency-free browser prototype for IHH Challenge 1. This is frontend work, not an installed clinical service.

## Run

From `frontend/`:

```bash
npm start
```

This uses Python 3's static server on port 4173, serving the repository parent directory so the local criteria and handoff links work. Navigate to the `/frontend/` path in your development browser. Alternatively run `python3 -m http.server 4173 --bind 0.0.0.0` from the repository root. Do not expose a server containing patient records publicly.

No npm installation, API keys, external fonts, or build step needed. Node.js is only needed for the npm shortcut and unit tests. Python 3 serves the files; the app is vanilla JavaScript/CSS with ES modules.

## What works

- Local PDF file validation (extension, size, basic PDF signature) and browser PDF preview. Parsing/rendering support ultimately depends on the browser; a PDF header check does not prove a valid, unencrypted PDF.
- Separate synthetic example with three source pages and three criterion checks.
- Six mock prefilled form fields; review/correction notes and source navigation.
- Finding review/filtering, source page navigation, zoom, rotation, and corrections.
- Human confirmation with rationale, reviewer and attestation; incomplete review and unsupported denial blocked.
- Editable unsent response; downloadable JSON review record including field edits and local event history.
- Responsive desktop/mobile layouts and visible keyboard focus.

## Mocked / unavailable

All demo text and findings are synthetic fixtures. Uploaded PDFs never inherit those findings. On the public static site, there is no OCR, AI service, full rule evaluation, insurance verification, server persistence, authentication, clinical audit, real sending, completed IHH PDF export, or measured time-saving result. The optional localhost backend now provides real text extraction/OCR, page search, review notes, and guarded clarification drafts; see ../backend/README.md. Approval is disabled because three checks cannot establish full eligibility. Form-field edits do not automatically recompute criterion findings; backend integration must add dependency invalidation.

Data stays in browser memory; refresh clears it. Download exports only the local demo review. No localStorage or remote upload. The app does not use event evaluation labels.

## Tests

```bash
npm test
```

Six Node unit tests cover confirmation guards, unknown/redacted preservation, denial rules, required rationale/attestation, upload limits, and fixture rule IDs/wording against the repo's criteria JSON.

Browser smoke tests: start the server, then `node tests/browser.cjs`. Requires Playwright and Chromium in your environment; set `PLAYWRIGHT_MODULE` to the installed module location if not on Node's module path, and `CHROMIUM_PATH` if Chromium is not `/usr/bin/chromium`. The test uses the repo's blank referral-form PDF (not a patient packet), writes synthetic screenshots/export under `/tmp`, and verifies upload validation, prefill corrections, source review, outcome guards, confirmation/export, session reset, and mobile overflow.

See [research, metrics and backend handoff](../docs/frontend-research-and-handoff.md) for sources, API contract, workflow semantics, priorities, and demo script.

## Publish updates

The public frontend uses GitHub Pages from the `gh-pages` branch. Source is on `codex/frontend-live`.

```bash
npm test
npm run deploy
```

The deploy command builds an explicit allowlist of static files into ignored `dist/` and pushes a new commit to `gh-pages` without switching or modifying the source index. Only app assets, the public criteria text, the handoff, and the temporary team-board data are published. No referral PDFs, ZIPs, OCR, or colleague case fixtures are included. GitHub can take a short time to rebuild; this is not automatic deployment on every source edit.

`frontend/team/tasks.json` is the shared temporary board data. Edit its status/assignees on `codex/frontend-live`, then use Refresh on the board; the board fetches that GitHub file and labels any fallback snapshot. The requested GitHub Project is not created: the integration can read projects but `createProjectV2` is denied. GitHub Issues is also disabled, and this integration cannot enable it.

## Local document-processing mode

Run the FastAPI service described in [backend/README.md](../backend/README.md), then open its root page locally. After selecting a permitted PDF, choose **Extract text with local backend**. This sends the file to the service on your own computer and enables real page images/text, search, review notes and an unsent next-step draft. It does not generate clinical fields or eligibility decisions. GitHub Pages remains static; it does not expose this localhost backend.
