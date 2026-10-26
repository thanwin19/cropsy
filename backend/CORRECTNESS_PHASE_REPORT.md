# Answer-correctness phase report (2026-10-17)

Scope kept: no new datasets or crops, same pipeline and models. Changes are in the verifier, citations, retrieval ranking, answer format and the chat card.
**Human expert review of agronomy: none.** Everything marked "checked" below was checked by automated tests or by me (an AI) reading the original passages.

## 1. Numbers, tables and context

| Failure (question) | Expected | Actual before | Root cause | Fix | Regression test |
|---|---|---|---|---|---|
| "கம்பு விதை அளவு எவ்வளவு" (pearl millet seed rate, Tamil) | Nursery 3.75 kg is per 7.5 cents; field rate 5 kg/ha; 12.5 kg/ha for shoot-fly areas | "3.75 to 12.5 kg per hectare" (nursery and field figures joined) | The chunk holds both rows; V2 only matched "per ha"; nothing compared the basis | `quantities.basis_mismatches` (verify V11): a figure keeps the basis the source gives it; handles Tamil word order and ranges | `test_nursery_rate_is_not_a_per_hectare_rate`, gold Q04/Q05 |
| "pearl millet seed rate" | Figures from the evidence | "increase to 10 kg per hectare" (source says 12.5) | V2's pattern never matched "per hectare" (only "per ha"), so no dose was ever compared | V12 `quantities.unsupported`: every weight, volume, cm and % must be in the passages of the crop asked about (g<->kg, ml<->l, acre<->ha only when the answer says acre) | `test_a_figure_not_in_the_evidence_is_reported` |
| "cowpea spacing" | Say the guide has no spacing | "30 x 10 cm" or "30 x 15 cm" (varied run to run: from the model's own knowledge) | Spacing in cm was not checked at all | V12 now covers cm, "A x B cm" and %; the second pass masks the figure and, if it was the headline, replaces the answer with a plain "not in the guides" | `test_spacing_and_percent_are_checked`, gold Q07 |
| "What is the seed rate for cowpea?" | Say the guide has no seed rate | "2 kg/ha" and "4 kg/ha" on different runs (2 kg/ha was phosphobacteria) | The figure existed, with the right basis, but for another purpose; a 3% acre/ha tolerance also let "4 kg" pass by coincidence with "10 kg" | V13 `purpose_mismatches`: a figure given as the seed rate, spacing or seed treatment must sit next to words of that purpose in the passage; acre conversion only when the answer says acre | `test_a_figure_for_another_purpose_is_not_a_seed_rate`, gold Q03 |
| "wheat seed rate per hectare" | 100 kg/ha, citing p134 | Right figure, cited p135 (a fertilizer page); the p134 line was not even retrieved | Seed-rate line sits at the end of a long variety-table chunk; its small window was diluted | Extra short "fact windows" for seed rate / spacing / sowing time lines (`embed_subchunks.py`, +163 windows, re-embedded) and a small bonus for chunks containing the question's phrase | gold Q01, retrieval eval |

## 2. Citations
Sources are now chosen from the passages that contain the answer's figures or dates (`quantities.support_score`: shared quantity 3, shared date or month 2; bare small numbers count nothing), best first, at most 3, one entry per page. If the answer says the evidence has no answer, nothing is cited. Fixes: wheat seed rate and sowing time now cite p134 (and p136 for the sowing depth), bengalgram p173 (was p177), cowpea no-answer cites nothing. Tests: `test_citation_is_the_page_that_contains_the_figure`, `test_date_claims_find_their_page`, gold citation column.
**Limit:** a passage that merely shares a figure with the answer is accepted as support; this checks presence, not that the sentence means the same.

## 3. Answer format and chat card
- The model prompt now asks for the direct answer in the first sentence with the specific product/quantity/time, forbids joining figures from different rows, and forbids disclaimers inside the answer.
- General guidance no longer opens with a long "not in the knowledge base" paragraph: description first, one short line after, and an amber "General guidance · not verified" badge.
- The region note is no longer appended to the answer text; it is one short note under the answer. The generic "Insufficient evidence" line is dropped when the answer is well supported or is general guidance; notes are de-duplicated.
- **The chat card had hidden the recommendation list whenever a headline answer existed** (steps, doses and timings never reached the farmer). Now shown as "What to do" (numbered). "Be careful" is shown for risks. The day-by-day "When" plan is shown only for a parcel (for general questions the model's schedule was not backed by evidence). Notes are one collapsible line; reference photos are collapsed ("tap to see photos"). Clear chat now also forgets the last crop.
- Checked in the browser: cowpea seed-rate no-answer, rice blast answer ("Use propineb 70% WP @ 1500-2000 gm/ha ..." then numbered steps), region box, follow-up.

## 4. Language
New tests `tests/test_language_cases.py` (about 60 parametrised cases: crop names in English, Tanglish and Tamil, typos, topic words, follow-up cues, ambiguous questions). Gaps found and fixed: "makkacholam", "gothumai"/கோதுமை missing; "manjal ilai yellow aaguthu" was read as turmeric (manjal = the colour here); Tamil "இதற்கு/இதன்" were not follow-up cues. Known ambiguity left: "kadalai" is read as groundnut (it can also mean chickpea); the answer names the crop it assumed.
Earlier fixes kept: "uram evlo podanum nel ku" is a rice fertilizer question; "ulundhu pooch marundhu" is blackgram insect control.

## 5. Retrieval (178 questions, 125 answerable)
| | Start of phase | Now |
|---|---|---|
| hit@1 | 0.840 | **0.888** |
| hit@3 | 0.928 | **0.952** |
| hit@5 | 0.952 | **0.976** |
| MRR | 0.884 | **0.920** |
| crop precision@5 | 0.973 | **0.998** |
Crop hit@3: wheat 0.5 -> 1.0, coconut 0.75 -> 1.0, bengalgram 0.5 -> 0.75; still weak: banana 0.833, ragi 0.75, sugarcane 0.8, cumbu 0.8, blackgram 0.923. Misses left: R15 (banana sun scald), R26 (Tamil sugarcane borer variety), R38 (blackgram DAP spray), G02 (ragi blast, rank 4), G04 (cumbu spacing, rank 5), G09 (bengalgram wilt). Method: a bonus for rare question words and for the phrase asked about (seed rate, spacing ...), a stronger preference for the crop asked about, and the fact windows above.
**Open ranking issue:** for "groundnut leaf spot" the web-portal pages (Alternaria, rust) rank above the guide's early/late leaf spot spray lines (p206). The answer is supported by a TNAU source but may not be the best one. The gold set accepts either.

## 6. Gold set (20 questions, `tests/gold_set.json`, runner `tests/run_gold_live.py`)
Expected values were read by me from the original passages (chunk ids in the file); not agronomist-reviewed. Latest runs: values 20/20, citation 20/20, behaviour 20/20 (two consecutive runs). Earlier runs on the same code line failed 1-3 questions because of model variation (for example cowpea seed rate answered 20, 4 or 2 kg/ha), so a pass today is not a guarantee for tomorrow's wording.

## 7. Results
| Check | Result |
|---|---|
| pytest | 222 passed (was 160; +62: language cases, quantity/citation/purpose tests, gold-set shape) |
| Routing eval | 105/105; 25/25 not blocked |
| Retrieval eval | see section 5 |
| Live behaviour checks | 69/69 (answer 28, general 30, abstain 2, answer_card 2, safety 4, clarify 2) |
| Gold set (live) | 20/20 on values, citations and behaviour |
| Chat smoke test | 38/38 |
| Frontend type check | clean |
| Browser | answer card, "What to do", notes line, region box, follow-up and cowpea no-answer checked. Voice (microphone blocked in the pane), photo and document upload through the browser were not retested this phase |

## 8. Automated versus human
- **Automated:** every number above (tests, evals, gold runner). They check that figures, bases, purposes, dates and pages match the retrieved passages; they cannot check that a TNAU recommendation is right for a farmer's field.
- **Read by an AI (me):** about 60 answers and the gold values. **Reviewed by a human expert: none.**

## 9. Remaining risks (priority order)
1. **Pesticide and dose correctness is still unverified.** The five pesticide-status entries, the paraquat flag and the three conflicts stay UNVERIFIED/unresolved. The new checks confirm a dose is in the guide, not that the product is currently registered or advisable (for example chlorpyriphos, flubendiamide in blackgram answers).
2. **Purpose check covers only seed rate, spacing and seed treatment.** Fertilizer dose vs. other doses, irrigation depth, and growth-stage mix-ups are not checked for purpose; V11/V12 would not catch a right number attached to the wrong stage.
3. **Table extraction can lose row/column headers.** Where the chunk text has no basis next to a figure, V11 deliberately does not flag it (to avoid false alarms), so an ambiguous table value can still pass.
4. **Tamil answers (Ministral 8B) still contain odd wording and conversions** (for example "1 cent (0.005 ha)"; 1 cent is about 0.004 ha). The numeric checks work on Tamil units but wording quality and terminology were not reviewed by a native speaker or a TNAU glossary.
5. **General guidance is unverified agronomy** (labelled, but unchecked; "approx." figures are the model's).
6. **Ranking:** web-portal pages can outrank the guide's own recommendation (groundnut leaf spot); banana, ragi, sugarcane retrieval still weak.
7. **Model variation:** the same question can produce different wording; V11-V13 reduce but do not remove wrong figures. Masked figures read "[amount: confirm with your KVK]".
8. Voice, photo and document upload in the browser: not retested (microphone blocked; file picker not drivable). Earlier API-level tests only.
9. Stored chat history in the browser keeps answers written by older versions of the app.

## 10. Files changed
`backend/app/quantities.py` (new), `app/steps/verify.py` (V11, V12, V13), `app/pipeline.py` (citations, notes), `app/steps/retrieve.py`, `app/steps/hybrid.py`, `app/steps/synthesize.py` (prompt, general guidance format), `app/steps/understand.py`, `app/steps/guides_dynamic.py`, `app/region.py`, `app/config.py`, `scripts/embed_subchunks.py`, tests (`test_quantities.py`, `test_language_cases.py`, `test_audit_regressions.py`, `gold_set.json`, `run_gold_live.py`), frontend `Phase7AdvisoryCard.tsx`, `cropsy-api.ts`, `store.tsx`.
