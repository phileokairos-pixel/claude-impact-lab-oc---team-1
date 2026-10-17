# Careward — Challenge 1 submission

## Who it helps
IHH intake coordinators reviewing hospital referral packets, with separate demo perspectives for hospital referral staff and the person receiving care.

## What we built
Careward organizes referral evidence, conflicting information, clarification requests, human review and onboarding next steps in one prototype. It makes unknowns visible instead of treating missing or redacted information as normal. The intended benefit is less searching and repeated review; time savings have not yet been measured.

## Guided team presentation (about 2 minutes 45 seconds)
Click **Present Careward** beside **Take a tour** on the live site. Speaker notes stay visible while each section opens and scrolls into view. Next/Back or arrow keys advance; Escape exits and restores the previous workspace. Motion respects reduced-motion settings.

- Neetal: the problem (0:00–0:20).
- Aaron: referral inbox and source evidence (0:20–1:05).
- Aaron: proposed model routing, illustrative API cost, time-saving scenarios and human checkpoints (1:05–1:50).
- Vibhu: clarification and onboarding coordination (1:50–2:20).
- Harjeev: proposed pilot, impact measurement and finished vision (2:20–2:45).

These are suggested timings, not an automatic timer. The walkthrough uses a separate synthetic review, does not submit a referral or confirm an outcome, and explicitly labels unfinished integration.

## Manual demonstration in three minutes
1. Open the live demo and choose DEMO-001 in Referral inbox. Explain open questions and the staff coordination checklist.
2. Open linked synthetic evidence review. Show the conflicting transfer evidence and original source pages. Review findings; preserve unknowns.
3. Record a clarification or clinical-review next step with reviewer confirmation. Continue to referral and onboarding; set the responsible team and next action.
4. Switch to Hospital referral staff to answer an open request. Return to IHH and show that new information requires fresh review.
5. Use Review packet to download and upload an invented six-page training PDF. The public site previews it. Demonstrate actual OCR only on the configured Python service; never claim the public site analyzed it.

## Real versus simulated
| Component | Status |
|---|---|
| Browser PDF preview and navigation | Working, including scanned training packet |
| PDF text extraction, OCR and page quality | Working Python service; not hosted by GitHub Pages |
| AI extraction adapter | Implemented; model credentials and validation required |
| Public referral inbox, role perspectives and questions | Synthetic session demo; role picker is not authentication |
| Human review, unknown/conflict handling, draft export | Working prototype; synthetic findings on public demo |
| Onboarding retention | Limited synthetic checklist metadata on this browser |
| Backend follow-up and authenticated shared records | Implemented modules and tests; not integrated with the public frontend workflow |
| Email, fax, CRM delivery and clinical eligibility approval | Not connected; no real messages or automatic admission |
| Render hosting | Configuration prepared; account deployment still required |

## How Claude is used
The team used Claude-assisted research, implementation and browser review during development. The optional runtime extraction adapter accepts configured Claude model output as an unreviewed draft, validates its shape and preserves source references for human review. The public synthetic walkthrough does not call a model.

## Run it
See [runtime instructions](demo-runtime.md) for Python, Tesseract, npm installation and model configuration. For static-only preview: `npm --prefix frontend ci`, `npm --prefix frontend run build`, then `python3 -m http.server 4176 --directory frontend/dist`.

## Known limits and next steps
Finish persistence and follow-up API/frontend integration; deploy the protected synthetic service; validate extraction and critical-field errors with IHH before measuring review time. Resolve remaining keyboard role-selection and responsive acceptance findings. Production use requires an approved identity provider, security review, retention decisions and validated clinical policy. The prototype does not connect to any IHH system.

## Data and license
The delivered demo fixtures are invented. Do not upload real client information. The repository is public and MIT licensed; see [LICENSE](../LICENSE). No demo video has been supplied; the live application is the demo link.
