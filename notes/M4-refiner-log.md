M4 11/18 · Refiner log

- Changed `DEFAULT_MODEL` to `ollama/qwen3.5:2b`. The shared `call_model()` in `models.py` hangs on qwen because LiteLLM leaves thinking on (no answer after 6+ min). Adding `reasoning_effort="none"` fixes it (2.2 s).
- `refine()` blanks each flagged phrase out of its sentence, has the model fill only the blank from the source facts, and rebuilds the sentence from the original text.
- `refine()` rejects any fill that changes text outside the blank or puts the wrong words back. It returns a faithful draft without calling the model.
- Furosemide: "Take your water pill 40 mg twice a day." -> "Take your water pill 40 mg daily." 6 of 6 test cases pass.
- Fixed the 2-sentence case (was 5 of 6): the model stuffed unrelated source facts into the blank ("daily, with potassium 3.1 (low)"), and the check matched the "." in "3.1" as the end of the sentence. Now the end of the sentence has to match the end of the reply, and the model only gets source facts that share a word with the sentence it's fixing.
- Real baseline drafts:
  - Fixed IDDM/NIDDM (-> "type 1"/"type 2").
  - Replaced "dialysis" with "insulin and glucose", which is also wrong.
  - Replaced 1 of 3 "Nerve Growth Factor" with "serotonin", also wrong (NA = noradrenaline).
  - Added the missing perphenazine fact to the clozapine draft.
  - No case changed text outside the flagged spots.
- Sending the whole draft failed: qwen removed 0 of 6 wrong phrases, echoed the prompt back, and took 9–14 s per draft.
- `timing.py`: `timed(func, *args)` times any agent call and logs timestamp, file, step (m1–m5), function, model, seconds, status, and notes to `results/latency_log.csv`.
- Latency: the baseline averaged 13.9 s on qwen and 6.1 s on gemma per PLABA abstract. `refine()` takes 0.3–1 s on short drafts and 0.6–7 s on long ones (was up to 12 s before the source fact filter).
- Open:
  - Fix the qwen hang.
  - Pass `atoms` to `refine()` in `pipeline.py`.
  - Wrap each pipeline node with `timed()`.
