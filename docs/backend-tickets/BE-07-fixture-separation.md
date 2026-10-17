# BE-07 · P0 before further sharing · Separate packet-derived data from source

Owner: backend teammate and team lead. Status: proposed. No dependency.

## Problem
The ZIP's README says its HTML contains packet-derived clinical summaries and requests organizer approval before sharing them in a repo. The archive is already committed on remote main. No organizer approval was established during this review. This is separate from checking whether records are de-identified.

## Scope
- Replace committed packet-specific fixtures with clearly synthetic examples.
- Load permitted local packet-derived results from an ignored/private runtime location; do not embed them in HTML or a public bundle.
- Remove evaluation labels from the live review payload and UI.
- Team lead should check the organizer's handling requirements for the already-shared archive and coordinate any remediation with collaborators. Do not rewrite Git history or force-push as part of this ticket without an agreed plan.

## Acceptance criteria
- Source/build artifacts contain no event packet images, OCR text, derived case summaries, or historical decision labels.
- Synthetic fixtures are explicitly marked and never substituted for uploaded-packet analysis.
- Ignore rules cover extracted results, OCR, PDFs, renders, logs containing clinical content, and local secret files.
- A documented organizer/team decision addresses the existing remote archive; a new ignore rule alone does not remove historical content.
