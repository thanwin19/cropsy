# Cropsy release status (2026-10-17)

Not yet farmer-ready. The two release blockers from the final review are fixed in code and tested; expert review and AWS staging are still outstanding.

## Fixed in this round
| Blocker | Fix | Tests |
|---|---|---|
| A dose was attached to the wrong pesticide (a number that exists in the guide, but for another chemical) | `quantities.dose_owners` ties every dose to the product written just before it, in the answer and in the evidence; verifier check V14 rejects an answer pairing (product, dose) that the evidence contradicts. First pass asks for a retry; second pass removes that sentence or step. Products that the guide itself lists at two doses (per pest or stage) get a note to check which applies. | `tests/test_product_dose.py` (8) |
| Parcel fertilizer totals mixed per-hectare and per-parcel figures | The parcel fertilizer answer is now written straight from the calculator (`calculator.answer_from_calculator`): each TNAU per-hectare recommendation with its page, then N, P2O5, K2O and urea, DAP, MOP totals for the parcel area. Missing, zero, negative or absurd areas give no totals. | `tests/test_fertilizer_calc.py` (5); browser: "answer matches the calculator" |

Also fixed while re-testing: a regression where a dose written once for a whole list ("carbendazim @ 500 g or IBP @ 500 ml/ha") was read as unlisted (ragi blast answers fell back to general guidance); a wrong-basis figure that survived the second verifier pass (pearl millet 3.75 kg per hectare, 0 of 8 runs after the fix); and off-topic or dangling sentences left after a figure was removed (cowpea spacing).

## Still open (not release-ready until done)
1. **Agronomist review** of pesticide and fertilizer advice. The five pesticide-status entries, the paraquat flag and the three recommendation conflicts remain UNVERIFIED. Doses are checked against the TNAU text, not against current CIB&RC labels.
2. **Tamil terminology** review by a fluent Tamil-speaking agronomist (a rice-blast answer used the Tamil term for stem borer).
3. **Voice** in the browser (microphone blocked in the test pane; the server transcription path was tested with a recorded clip).
4. **Outside photos** are matched by title, not by what the picture shows.
5. **Comparison answers** are written as sentences, not a table.
6. **AWS staging** (deployed services, IAM, model access, storage, logs) not done.

## Known limits
- The per-hectare totals use urea 46% N, DAP 18-46-0 (its N credited), MOP 60% K2O; split applications are described by the TNAU guide, not computed.
- A pesticide dose that the guide gives at two values for different pests is shown with a "check which applies" note, not resolved.

## Release-candidate freeze and staging prep (2026-10-17)
- Frozen: `RELEASE_CANDIDATE_MANIFEST.txt` (file hashes of app, tests, knowledge, review packets). Offline suite after the last change: pytest 267 passed.
- Staging defect fixed: Textract, Bedrock (photo) and Transcribe clients hardcoded the SSO profile and region and would fail on a deployed role; they now use the shared session (profile if present, otherwise the role). CORS accepts `CROPSY_CORS_ORIGINS`. Tests: `tests/test_aws_session.py`.
- Written: `STAGING_CHECKLIST.md` (env vars, IAM, timeouts, limits, post-deploy tests); `expert_review/AGRONOMIST_REVIEW_PACKET.md` and `TAMIL_REVIEW_PACKET.md` (blank sign-off fields; reviewed corrections go into the regression tests).
- NOT done: the live gold/universal repeat runs after a clean restart. The AWS SSO login expired, so a live gold run on 2026-10-17 scored 8/20; that result is invalid (credential failure), not a regression. Re-run after `aws sso login`.
- NOT done: expert reviews (need people), the AWS deployment (needs approval and credentials). Production decision: HOLD.

## Clean-restart verification (2026-10-17, after SSO re-login)
Backend restarted, AWS identity confirmed. Logs in `test_runs/`.
- Gold set: 20/20 on numbers, citations and behaviour in 3 of 3 clean runs (plus 1 earlier), so 4 of 4. The intermittent blackgram Q10 failure did not recur; it is not explained, only unobserved.
- Universal live set (68 checks): 1 failure, U11 (Tanglish "manjal ku basal ah FYM evlo podanum?"): the answer had no sources. Re-run alone 3 of 3 passed, so it is intermittent. Turmeric basal FYM is also a registered recommendation conflict (25 t/ha TNAU vs 10 t Spices Board), so the variation may be the conflict handling; the agronomist packet covers it.
- Comparison tables: deferred until expert review and this verification are complete (owner's decision).
