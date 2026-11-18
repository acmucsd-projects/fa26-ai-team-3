"""M5 (Laura): polish v3 experiment.

v2 lowered the grade but summarized away facts (129 words, only 20% of numbers kept),
probably because of its rule "do not make it longer than the DRAFT".
v3 keeps v2's rules that worked (no markdown, no greeting, short sentences, exact numbers)
but drops the length rule and explicitly forbids summarizing.

Run from the repo root, with Ollama open:   python week4/m5_polish_v3.py
Optional quick test on 2 outputs:            python week4/m5_polish_v3.py 2
Output: results/m5_polish_runs_v3.csv, plus a v1 / v2 / v3 comparison table.
"""
import re, sys, time
import pandas as pd
import textstat as ts
from clearmed.models import call_model, DEFAULT_MODEL
from clearmed.eval_harness import meets_readability_target

PROMPT_V3 = (
    "You rewrite health text so a patient with an 8th-grade reading level can understand it.\n"
    "Rules:\n"
    "1. Keep EVERY fact and EVERY sentence's meaning. Do not summarize or skip details.\n"
    "2. Copy all numbers, percentages, doses, frequencies, dates, years and drug names exactly.\n"
    "3. Do NOT add anything that is not in the DRAFT: no new advice, causes, reassurance or examples.\n"
    "4. Use short sentences (15 words or fewer). Split long sentences instead of cutting content.\n"
    "5. Use everyday words. If a medical term must stay, keep it and add a short plain meaning in parentheses once.\n"
    "6. Plain text only: no greeting, no headings, no bold, no bullet points, no questions to the reader.\n"
    "7. The result may be about as long as the DRAFT. That is fine.\n"
    "Return only the rewritten text."
)

def strip_markdown(text):
    text = re.sub(r"[*#>`_]+", "", str(text))
    lines = [l.strip(" -•\t") for l in text.splitlines() if l.strip()]
    return " ".join(l if re.search(r"[.!?:]$", l) else l + "." for l in lines)

def real_numbers(text):
    """Numbers in the text, ignoring list numbering like '1.' at the start of a line or 'Step 2'."""
    text = str(text)
    text = re.sub(r"(?m)^\s*\d+[.)]\s", " ", text)
    text = re.sub(r"(?i)\b(step|option|part|tip|point)\s+\d+", " ", text)
    return set(re.findall(r"\d+(?:\.\d+)?", text))

def score(rows_df, label_col="version"):
    out = []
    for _, r in rows_df.iterrows():
        src = baseline.loc[r.row]
        before, after = strip_markdown(src.output), strip_markdown(r.polished)
        nums = real_numbers(src.output)
        out.append({
            "version": r[label_col], "id": r.id, "baseline_model": r.baseline_model,
            "fk_before": ts.flesch_kincaid_grade(before), "fk_after": ts.flesch_kincaid_grade(after),
            "smog_after": ts.smog_index(after),
            "words_before": ts.lexicon_count(before), "words_after": ts.lexicon_count(after),
            "meets_after": meets_readability_target(after),
            "real_numbers_kept": len(nums & real_numbers(r.polished)) / len(nums) if nums else None,
            "markdown_left": bool(re.search(r"\*\*|^#|^\s*[*-] ", str(r.polished), re.M)),
            "seconds": r.seconds,
        })
    return pd.DataFrame(out)

baseline = pd.read_csv("results/baseline_log.csv", dtype={"id": str})
N = int(sys.argv[1]) if len(sys.argv) > 1 else len(baseline)

runs = []
for i, row in baseline.head(N).iterrows():
    start = time.time()
    out = call_model(PROMPT_V3, f"DRAFT:\n{row.output}", model=DEFAULT_MODEL)
    runs.append({"row": i, "id": row.id, "baseline_model": row.model, "version": "v3",
                 "seconds": round(time.time() - start, 1), "polished": out})
    print(f"{i+1}/{N}  {row.id}  {runs[-1]['seconds']}s")
    pd.DataFrame(runs).to_csv("results/m5_polish_runs_v3.csv", index=False)  # saved after every output

v3 = pd.DataFrame(runs)
old = pd.read_csv("results/m5_polish_runs.csv", dtype={"id": str})
old = old[old.row.isin(v3.row)]                       # compare on the same outputs
allruns = pd.concat([old, v3], ignore_index=True)
scores = score(allruns)
cols = ["fk_before", "fk_after", "smog_after", "words_before", "words_after",
        "meets_after", "real_numbers_kept", "markdown_left", "seconds"]
print("\nHuman PLABA rewrite averages ~187 words, FK ~11.9. Target: >= 80% meet grade 8.\n")
print(scores.groupby("version")[cols].mean().round(2).to_string())
scores.to_csv("results/m5_polish_scores_v1_v2_v3.csv", index=False)
