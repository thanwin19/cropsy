# Cropsy chatbox correctness audit (2026-10-17)

Scope: the existing pipeline and models, unchanged. No vegetable batch ingested, no permission request sent. Every answer below was read by me (an AI). **No agronomist or extension officer has reviewed any of it.** The automatic checks are mechanical.

## Method
Baseline from the running backend, then real questions sent through `/api/advisory` (English, Tamil, Tanglish, typos, follow-ups, parcel and satellite, other regions, missing crops) and through the real chat in the browser. For each answer I read the answer, recommendations, sources, limitations and confidence, and compared them with the retrieved passages.

## Failures found (question / expected / actual / root cause / fix / regression test)

| # | Question | Expected | Actual before | Root cause | Fix | Test |
|---|---|---|---|---|---|---|
| 1 | "What is the seed rate for cowpea?" | Say the guide has no seed-rate line; cite nothing | Said "not specified" but cited page 169 | Sources were built from retrieved chunks whatever the answer said | `_build_sources` returns no sources when the answer says the evidence has no answer (`pipeline._NO_ANSWER_RX`, also used by the confidence rule) | `test_no_source_is_cited_beside_a_no_information_answer`; G08 is now an `abstain` live check |
| 2 | "uram evlo podanum nel ku" (how much fertilizer for rice) | Fertilizer dose for rice | Answered with sowing time / water management | The English rewrite by the model turned "uram" into water management | Farmer's own topic words (uram, pooch/poochi, marundhu, noi, vithai, kalai, aruvadai and Tamil forms) are checked; the rewrite is rebuilt when it lost the topic (`understand._topic_from_words`) | `test_tanglish_fertilizer_word_is_not_read_as_water` |
| 3 | "ulundhu pooch marundhu" (blackgram insecticide) | Insect control for blackgram | Answered "flowers open at 60-65 days" | Same | Same | `test_tanglish_insect_medicine_is_a_pest_question`, `test_medicine_alone_asks_for_a_spray` |
| 4 | "tomato ku enna marundhu adikkanum" | Spray advice | "tomato how to grow it" | Same | Same | same |
| 5 | "rice blast control" | The blast sprays on top | A variety note ranked first, the spray chunk sixth | A short query matches any chunk mentioning the word; no weight on a rare, specific word | Small bonus (max 0.06) for chunks that contain rare words from the question (`hybrid.term_bonus`); reorders only, the cosine score used for sufficiency is untouched | `test_rare_question_word_lifts_the_chunk_that_contains_it`, retrieval eval |
| 6 | "TM-05 satellite health this week" (API call without parcel_id) | Parcel evidence with date and index | General advice about tomato hornworms | The web app extracts the parcel id; the API did not | `pipeline.run` uses a parcel named in the words (`tools.parcel_from_text`) | `test_parcel_named_in_words_is_found` |
| 7 | "TM-999 satellite" | Say the parcel does not exist | General rice advice | No such parcel; fell to general guidance | Clarify card "parcel not found" | live check |
| 8 | "and the spacing?" after a wheat answer | Answer for wheat | "Which crop?" or rice/maize figures | No follow-up memory | Frontend sends the crop of the previous answer (`context_crop`); backend uses it only for a short question with a follow-up cue and no crop of its own | `test_followup_detection_needs_a_cue_and_no_crop`; checked in the browser |
| 9 | "what is the seed rate" (no crop) | Ask which crop | Rice and maize figures | Only fertilizer amounts triggered the crop question | Seed rate, spacing, variety, sowing time, harvest time also ask which crop | `test_crop_dependent_question_without_a_crop_asks_which_crop` |
| 10 | (screenshot) region box hidden behind the input bar; "Sprayer tank" shown on "125 kg per hectare" | Box visible; no sprayer for fertilizer or seed | Clipped box; sprayer menu | Popover clipped by the input bar; dose card assumed every dose is a spray | Portal for the popover; sprayer only for per-litre doses | checked in the browser |

## Before and after
| Check | Before | After |
|---|---|---|
| pytest | 151 passed | 160 passed (9 new regression tests) |
| Routing eval | 105/105; 25/25 not blocked | 105/105; 25/25 |
| Retrieval, 178 questions / 125 answerable | hit@1 0.784, hit@3 0.904, hit@5 0.936, MRR 0.844, crop precision@5 0.95+ | hit@1 **0.840**, hit@3 **0.928**, hit@5 **0.952**, MRR **0.884**, precision@5 0.973. Misses 12 -> 9 (R02, R16, R37 fixed, none added) |
| Live behaviour checks | 68/69 (G08 failing) | 69/69 (G08 now an abstain check) |
| Chat smoke test | 38/38 | 38/38 |
| Frontend type check | clean | clean |

Weak crops by hit@3 now: bengalgram 0.5, wheat 0.5, ragi 0.75, coconut 0.75, cumbu 0.8, sugarcane 0.8, banana 0.833. The same misses remain: R15, R26, R38, U08, G02, G04, G09, M11, B11 (mostly seed-rate and variety-table lines).

## Checked and found acceptable (by my reading only)
Wheat sowing time, wheat seed rate (100 kg/ha, printed beside the variety table on the guide page), bengalgram seed rate (90 / 75 kg/ha), cowpea spacing, ragi blast carbendazim, groundnut leaf spot, fall armyworm in maize, price question (fixed "no live prices" card), "which fertilizer" (asks the crop), "my crop is dying" (general guidance, labelled), rice and tomato questions about Kerala/Punjab (labelled general guidance for other regions, no Tamil Nadu card), satellite answer for TM-05 and TM-12 (date, index value, baseline, limitation about not diagnosing causes).

## Not fixed: risks, in priority order
1. **Pesticide and dose correctness is unreviewed.** The five pesticide-status entries, the paraquat flag and the three recommendation conflicts remain unverified and unresolved. Example: a blackgram answer recommends chlorpyriphos, flubendiamide and others as printed in the 2020 guide; their current registration was not checked.
2. **Synthesis can misread tables.** Pearl millet (Tamil question): "3.75 to 12.5 kg per hectare" mixed the nursery rate (3.75 kg for 7.5 cents) with the shoot-fly rate (12.5 kg/ha). The English answer was more careful. The verifier cannot see this kind of mix-up.
3. **Page citation can be one page off** (wheat seed rate cites page 135; the figure is on page 134).
4. **Headline answers are sometimes generic** ("use integrated practices and appropriate fungicides"); the specific sprays are in the recommendations list. Check the recommendation list is always visible in the chat.
5. **General guidance is unverified agronomy.** It is labelled, but nobody has checked, for example, the "moderate" phosphorus reading of 12 kg/ha in the document explanation.
6. **Tamil answer quality** is readable but unreviewed by a native speaker or TNAU glossary.
7. **Photo:** the test photo is probably in the reference set, so its match is not an independent test. The caption said "brown spots" while the match was powdery mildew (white powder): captions and references can disagree.
8. Small wording issue: the "parcel not found" and some fixed cards still carry a generic "Fixed, reviewed guidance ... Forest Department" limitation line.
9. Old chat history stored in the browser shows answers from before the wheat ingestion (for example wheat sowing as "general guidance"); new questions are correct.

## Tests I could not complete
- **Voice:** the browser pane blocks the microphone; not tested this session.
- **Photo and document upload through the browser:** the file picker cannot be driven here. I tested the same backend paths by API only: a blackgram photo (see risk 7) and a generated soil-report image (Textract read it correctly; the explanation was faithful to the numbers).
- **Native-speaker Tamil review, agronomist review, pesticide registry confirmation:** not done; none can be done by me.

## Human review versus automatic checks
Human expert review: **none**. Automatic: pytest, routing eval, retrieval eval, live behaviour checks (pattern checks on answers), smoke test, type check. My own reading of about 40 answers is a first pass, not an expert review.
