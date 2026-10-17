# BE-06 · P1 after the working slice · Instrument timing and rehearse end to end

Owner: backend teammate plus frontend owner. Status: proposed. Depends on BE-01–04.

## Goal
Measure whether automation reduces real review work without hiding mistakes or waiting. User-reported baseline is approximately 120 minutes; 90/60/30 minutes are targets for 25/50/75% less time, not measured results.

## Scope
- Record receipt, processing stages, first review, pause/resume, corrections, clarification, escalation, and final disposition with packet/run versions.
- Distinguish active coordinator time from elapsed time and hospital/authorization waiting.
- Add an end-to-end test of upload → analysis → evidence → correction → confirmation → unsent export, plus failure and restart scenarios.
- Rehearse with a permitted new packet and document what works vs remains mocked.

## Acceptance criteria
- Durations use consistent timestamps and exclude explicit pauses from active time; unknown/missing intervals are not zero.
- Clarification is an intermediate state, not a completed approval/denial in turnaround metrics.
- Failed/unfinished jobs are reported, not removed to improve the average.
- Compare manual/assisted work of equivalent scope; report sample size and quality checks. No savings percentage inferred from a synthetic UI demo.
- End-to-end test confirms correct page citations and that corrected data invalidates stale decisions.
- Runtime instructions and demo script work from a clean checkout with secrets supplied outside Git.
