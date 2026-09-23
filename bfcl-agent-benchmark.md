# BFCL subset

## Goal

Run fixed, auditable 50-task BFCL `simple_python` and 50-task `multiple` subsets through Yuxi's local agent harness.

## Tasks

- [x] Prepare 50 matched records and ground truth from BFCL revision `6ea57973c7a6097fd7c5915698c54c17c5b1b6c8` → verify manifest hashes and Apache-2.0 source note.
- [x] Run a 5-task Qwen2.5 7B smoke → verify zero runner errors and inspect parsed calls.
- [x] Run all 50 tasks → verify sample count, tool-selection and argument-exact metrics.
- [x] Update benchmark lock/README/thesis only if the full artifact is valid → verify hashes and tests.
- [x] Repeat the fixed preparation and scoring for `multiple` → verify 50 records and zero call errors.
- [x] Extend the adapter to BFCL `parallel` output forms and score 50 tasks → verify parser tests and zero call errors.

## Done when

- A fixed 50-record artifact, result JSON, source revision, license and reproducible commands are recorded.
- The adapter tests pass and no benchmark process remains running.
