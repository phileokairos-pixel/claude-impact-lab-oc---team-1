# Running the interface and processing service together

Owner: Aaron (runtime/integration). Vibhu keeps #22 persistence/API ownership;
Harjeev keeps #23 follow-up service ownership. Do not remove host/origin guards.

GitHub Pages hosts static files only. It cannot run FastAPI, Tesseract or a model
adapter. The current frontend intentionally discovers the API only when loaded
from its same-origin localhost server. A successful Pages deployment does not
connect processing.

## Presentation-laptop setup (macOS/Linux, Python 3.12+, Node 22+)

From the latest Team 1 integration checkout:

```bash
npm --prefix frontend ci
python3 -m venv .venv
. .venv/bin/activate
python3 -m pip install -r backend/requirements.txt
```

Install Tesseract with the platform package manager (macOS: `brew install tesseract`;
Debian/Ubuntu: `sudo apt install tesseract-ocr`). Then:

```bash
python3 -m backend.demo_runtime --check
python3 -m backend.demo_runtime
```

Open the server root printed by the launcher in the presentation laptop's browser,
not the GitHub Pages tab. Select Review packet, upload the invented training PDF,
and select Extract text with local backend. The server supplies both the interface
and processing API; access logs are disabled. Try the scanned version to test OCR.
The starter is deliberately localhost-only and defaults to no model calls.

## Real model-backed extraction

Install `backend/requirements-analysis.txt`. Configure ANTHROPIC_API_KEY and
IHH_ANALYSIS_MODEL securely on that same machine, never in the browser or Git.
Choose an actually available model ID; do not invent one. Run:

```bash
python3 -m backend.analysis check-model
python3 -m backend.demo_runtime --analysis --check
python3 -m backend.demo_runtime --analysis
```

The preflight checks configuration presence, not model access or clinical accuracy.
The check-model command makes a provider request. Test invented packets first;
manual source verification remains necessary. Never label OCR as completed AI
analysis, or test-fixture output as actual extraction.

## Public backend dependency

This cloud environment currently has no hosting identity, model secret or public
service publishing tool configured. Model-provider network access is not currently
allowlisted. A public demo needs a chosen hosting service, a team-authorized account,
HTTPS/same-origin routing and an appropriate access boundary before uploads are
exposed. Configure provider access through the environment settings; do not bypass
network policy. Keep the GitHub Pages synthetic demo available meanwhile.

The launcher does not implement durable/shared records (#22), follow-up documents
(#23), authenticated identities (#27) or live clinical validation (#26). Do not
claim that a localhost launch closes those tickets.

## Render deployment (prepared; requires your account)

The repository now includes `render.yaml` and `Dockerfile`. In Render, create a
Blueprint from Team 1 and select **codex/frontend-live**. Review the free service
plan before deploying; free services can sleep, so warm it up before presenting.
If a paid plan is required, stop for the account owner's choice.

Render supplies RENDER_EXTERNAL_HOSTNAME. The Blueprint generates
CAREWARD_DEMO_PASSWORD; retrieve it privately from the service environment in the
Render dashboard. Sign in to the new HTTPS service with username `careward` and
that password. Do not paste it into chat, commit it, or put it in the URL.

The public instance is a shared synthetic demonstration, not staff authentication:
- all application/API/document routes require the shared password; /ready exposes
  only a minimal health response for Render;
- upload accepts only the exact two reviewed downloadable invented PDFs;
- hostname and cross-origin write checks remain enforced;
- records are temporary and disappear on restart; no production client data allowed.

Default mode has real PDF text extraction/OCR but no AI calls. Optional real
extraction needs ANTHROPIC_API_KEY, IHH_ANALYSIS_MODEL and
IHH_ANALYSIS_ADAPTER=backend.extraction:create_adapter set securely in Render.
No API key is bundled into the frontend. Verify the model and source citations
before presenting model output as working. Use the Render URL for processing;
the GitHub Pages URL remains the static frontend.

After deployment, verify: protected landing page → successful login → connected
service notice → upload text PDF → six source pages → scanned PDF OCR → rejection
of any other upload → no unauthenticated API/document access. Keep the original
Pages site available as the synthetic walkthrough fallback.
