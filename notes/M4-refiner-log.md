M4 11/18 · Refiner log

- Changed `DEFAULT_MODEL` to `ollama/qwen3.5:2b`. The shared `call_model()` in `models.py` hangs on qwen because LiteLLM leaves thinking on (no answer after 6+ min). Adding `reasoning_effort="none"` fixes it (2.2 s).
- `refine()` blanks each flagged phrase out of its sentence, has the model fill only the blank from the source facts, and rebuilds the sentence from the original text.
- `refine()` rejects any fill that changes text outside the blank or puts the wrong words back. It returns a faithful draft without calling the model.
- Furosemide: "Take your water pill 40 mg twice a day." -> "Take your water pill 40 mg daily." 5 of 6 test cases pass.
- Real baseline drafts:
  - Fixed IDDM/NIDDM (-> "type 1"/"type 2").
  - Replaced "dialysis" with "insulin and glucose", which is also wrong.
  - Left the clozapine blanks empty.
  - No case changed text outside the flagged spots.
- Sending the whole draft failed: qwen removed 0 of 6 wrong phrases, echoed the prompt back, and took 9–14 s per draft.
- `timing.py`: `timed(func, *args)` times any agent call and logs timestamp, file, step (m1–m5), function, model, seconds, status, and notes to `results/latency_log.csv`.
- Latency: the baseline averaged 13.9 s on qwen and 6.1 s on gemma per PLABA abstract. `refine()` takes 0.3–1 s on short drafts and 0.5–12 s on long ones.
- Open:
  - Fix the qwen hang.
  - Pass `atoms` to `refine()` in `pipeline.py`.
  - Wrap each pipeline node with `timed()`.
