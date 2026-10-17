# BE-02 · P0 · Implement OCR with stable page citations

Owner: backend teammate. Status: proposed. Depends on BE-01 for jobs; parser can be built independently.

## Problem
OCR is currently a README instruction. `blind_eval.py:44` renumbers the remaining pages if any OCR file is missing, so evidence can reference the wrong PDF page. The real sample form also differs from the standalone blank form.

## Scope
- Render pages and extract text through OCR or a supported document-vision approach.
- Preserve 1-based original PDF page IDs regardless of extraction failures, duplicate detection, sorting, or rotation.
- Expose page images/PDF access through the local service for the evidence viewer.
- Keep original and corrected orientation distinguishable; support skewed scans, handwriting, checkboxes, and multiple form layouts.
- Return per-page quality/error flags; represent unreadable, blank, and redacted separately where detection is reliable.

## Acceptance criteria
- Synthetic files for pages 1 and 3 produce markers PAGE 1 and PAGE 3, never PAGE 2; add a regression test.
- A failed page remains in the document manifest with its original index and explicit failure.
- Every citation's page opens the correct source page; normalized bounding boxes, if supplied, have a defined orientation and coordinate convention.
- Low-quality extraction is flagged, not silently treated as a clinical fact.
- No reconstruction of redacted identity/date fields. OCR output remains outside Git and logs avoid patient content.

## Frontend handoff
Manifest: `documentId`, `page`, `imageUrl`, rotation, quality, and extraction state. Preserve exact page numbers in the analysis output. An initial release can cite whole pages; bounding-box highlighting can follow.
