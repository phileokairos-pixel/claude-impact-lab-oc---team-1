# Backend tickets — Team 1

Review date: October 17, 2026. Reviewed `referral-review-repo.zip` in remote `main` at commit `c3e9a36c2b208b24cbde861cbb2cc33495e597b0`. ZIP was safely extracted outside the checkout; colleague's files were not edited. Owner for all tickets: backend teammate (GitHub username not provided).

**Status: proposed / not started.** These are ready-to-copy issue bodies, not published GitHub issues. A read-only GitHub API check returned Forbidden, so issue creation is unavailable here. Git read access works independently of GitHub API access.

## What exists

- A static HTML review page with hardcoded packet summaries, rule findings, actual IHH decisions, and response templates.
- A Python script that calls Anthropic on pre-generated OCR text and a separate scoring function.
- No upload endpoint, OCR pipeline implementation, job service, result adapter, protected document viewer endpoint, or server-side review workflow.

## Recommended order

| Priority | Ticket | Deliverable | Dependency |
|---|---|---|---|
| P0 | [BE-01: Runnable local API and job lifecycle](BE-01-api-and-runtime.md) | PDF upload → job ID → status/error | None |
| P0 | [BE-02: OCR and original-page provenance](BE-02-ocr-and-pages.md) | Page images/text with stable original numbers | BE-01; parser can be developed independently |
| P0 | [BE-03: Validated extraction and criteria contract](BE-03-analysis-contract.md) | Source-backed form fields and findings | BE-02 |
| P0 | [BE-04: Review and outcome guards](BE-04-human-review.md) | Reviewed corrections, guarded decisions, editable unsent draft | BE-03; synthetic tests can start now |
| P0 before accuracy claims | [BE-05: Blind evaluation and reproducibility](BE-05-evaluation.md) | Uncontaminated, versioned results with correct denominators | BE-03 |
| P1 after a working slice | [BE-06: Timing and end-to-end regression](BE-06-measurement.md) | Reproducible demo and evidence for time-saving claims | BE-01–04 |
| P0 before sharing further | [BE-07: Separate packet-derived fixtures from source](BE-07-fixture-separation.md) | Synthetic committed examples, local private fixtures | None |

**First milestone:** one permitted PDF → real job progress → actual extracted fields/findings with page citations → coordinator corrections → clarification draft. Keep approval disabled until applicable criteria coverage and review requirements are implemented. Do not spend today on EHR integration, real fax delivery, payer integrations, or production deployment.

Frontend owner can build against the BE-03 response contract immediately. The frontend currently lives in `frontend/`, and the broader design/research contract is in `docs/frontend-research-and-handoff.md`. Existing frontend code is local and not yet pushed; coordinate integration on one agreed commit.

## Confirmed review findings

1. **P0 — unsafe/stale approval draft.** `referral-review.html:233–247` enables both decisions based only on checkbox acknowledgement. Browser reproduction: tick the flags on the initial case; a failed rule remains, Approve becomes enabled, and the draft says acceptance is possible. Uncheck a flag afterward: the existing approval draft remains. This is acknowledgement, not resolution or documented override.
2. **P0 — missing live pipeline.** HTML uses hardcoded `P` records, with no API call or PDF/source viewer. `blind_eval.py` requires OCR text prepared elsewhere. There is no connection from a new uploaded packet to displayed results.
3. **P0 — citation shift.** `blind_eval.py:41–44` labels pages with enumeration rather than filename page numbers. Synthetic reproduction with `_p-01.txt` and `_p-03.txt` labels the latter PAGE 2.
4. **P0 — unvalidated analysis schema.** `blind_eval.py:33–35,54–55` parses JSON but does not validate required fields, enums, rule IDs, page bounds, citations, or full coverage. Model schema uses `fails`, while HTML expects `fail`; model rules are objects while HTML expects arrays. No adapter exists.
5. **P0 for honest evaluation — label-contaminated static examples.** HTML embeds actual IHH outcomes and explicitly says its suggestions were written after the decision file had been opened (`:244–245`). The separate suggestion function does not read labels; that is useful, but it does not make the existing HTML fixtures blind results.
6. **P1 — setup/reproducibility gaps.** Import-time API client and criteria loading also affect score-only execution; criteria autodiscovery does not match this repository if extracted at its root. Default model must be verified against the team's actual access. No dependency pinning or API credentials are configured in this environment. Cached suggestions are skipped solely by filename (`:51`), irrespective of changed packet text, criteria, model, or prompt.
7. **Sharing boundary.** ZIP README itself says packet-derived embedded summaries need organizer review or should be loaded from an ignored file. The archive is already on remote `main`; no organizer permission was established here. Do not copy those summaries into our new frontend or ticket examples. No destructive Git-history changes were made.

## Checks actually performed

- Inspected archive contents and Python/HTML source; Python syntax parses.
- Ran local browser checks for decision gating and stale draft behavior; counted zero embedded PDF viewers/source links.
- Ran isolated `packet_text` function with synthetic OCR filenames to reproduce citation renumbering.
- Checked only the evaluation label vocabulary: `approve` and `deny` match the script's suggestion vocabulary. No label-name mismatch is reported.
- Did not execute live model inference: Anthropic SDK and API key are absent in this machine. No real packet was submitted to a model as part of this review.
- Did not establish clinical correctness of the colleague's embedded summaries or citations. This is a code/workflow review, not a packet-level medical assessment.
