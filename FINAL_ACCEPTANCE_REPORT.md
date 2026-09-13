# Final Acceptance Report

## 1. Environment

- Project root: repository root
- Python: 3.13.5
- pip: 26.0.1
- Dependencies: available; no installation was required for this acceptance run.

## 2. Static Checks

- `python -m compileall .`: PASS
- `ruff check .`: PASS

## 3. Offline Tests

- `pytest -q`: PASS
- Result: 140 passed, 6 skipped, 0 failed.
- Skipped tests are opt-in live semantic tests and do not access the network by default.

## 4. Business Matrix

| Area | Status | Evidence |
| --- | --- | --- |
| Stage S0-S5 | PASS | Deterministic stage and regression tests cover S0-S5 plus S2/S4/S5 negative boundaries. |
| Budget | PASS | Separate budget-existence and amount-certainty validation tests pass. |
| Decision Maker | PASS | Authority-evidence positive and negative tests pass. |
| Influencer | PASS | Explicit evaluation influence is required; meeting attendance alone is rejected. |
| Timeline | PASS | Explicit, uncertain, conflicting, and timeline-only conflict cases pass. |
| Conflict | PASS | `affected_fields` is tested as the execution source of truth. |
| Risk | PASS | Competition, validation, technical requirement, information-gap, and semantic de-duplication tests pass. |
| Action | PASS | Seller, customer, both, pending-time, and AI-recommendation separation tests pass. |
| Completeness | PASS | Deterministic completeness tests read final validated results. |

## 5. Input Handling

| Input | Status |
| --- | --- |
| Text | PASS |
| Image postprocessing | PASS |
| Text PDF | PASS |
| Scanned PDF | PASS |
| Mixed PDF | PASS |
| Bad input and upload limits | PASS |

## 6. Live Semantic Tests

SKIPPED — no `OPENAI_API_KEY` was configured in the acceptance shell. Live tests remain opt-in through `RUN_LIVE_TESTS=1 pytest -m live -q`.

## 7. Streamlit

PASS — an isolated Streamlit startup on port 8502 returned HTTP 200. The existing local service on port 8501 also returned HTTP 200.

## 8. Security

- Submission ZIP contains secrets: NO
- Submission ZIP contains cache files: NO
- Submission ZIP contains development residual files: NO
- ZIP path: `dist/opportunity-copilot-submission.zip`

## 9. Hard-code Audit

Production fixture-specific hard-code found: NO.

## 10. Remaining Blockers

None identified for offline submission and local interview demonstration.

## 11. Final Recommendation

READY TO SUBMIT
