# Cropsy field test sheet (for an agronomist or extension officer, and 5 to 10 farmers)

Purpose: find out where Cropsy is wrong or unclear with real users before relying on it. Nothing here has been done yet. All parcel data in the app is dummy; use the farmer's real field only by typing the crop and stage in the question.

## A. Agronomist review (30 to 40 minutes)
1. Open the app and ask the 12 questions in `backend/tests/run_queries.py` (or your own 12). For each answer mark: Correct / Partly / Wrong / Unsafe.
2. For every answer with a dose or chemical, check the number against the TNAU source shown. Mark any that differ.
3. Check the spread scan for one rice parcel: are the wind-borne disease, the 1,200 m reach and the 72 hour horizon reasonable for Then Malai? Write the numbers you would use instead.
4. Fill `backend/tests/expert_rationales.json` for the evidence-check set (what the right answer is and why).
5. Read 10 Tamil replies: Natural / Understandable / Confusing.

## B. Farmer session (15 minutes each)
Give the farmer a phone. Do not explain the screens. Ask them to:
1. Ask a question about their crop in their own words (Tamil, Tanglish or English).
2. Send a photo of a leaf problem.
3. Find which parcel needs attention first.
4. Open the map and play the epidemic demo. Ask: "What is the orange line? What would you do?"

Record: time to first answer, words they used that the app did not understand, where they hesitated, whether they trusted the answer and why, and what they would do next.

## C. Pass criteria to decide before the test
- At least 80 percent of agronomist-rated answers are Correct or Partly with no Unsafe answer.
- Every dose matches its source.
- At least 7 of 10 farmers complete tasks 1 to 3 without help.
- Any Unsafe answer is a stop-and-fix item, whatever the average.

## D. After the test
Add each failed question to `backend/tests/eval_set.json` so it cannot regress, and log officer corrections in the app.
