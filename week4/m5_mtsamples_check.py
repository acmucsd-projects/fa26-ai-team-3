"""M5 (Laura): does polishing keep the facts that matter in REAL clinical notes?

PLABA abstracts are research papers. ClearMed's real input is clinical notes, where the facts
that matter are doses, frequencies and instructions. This script:
  1. Re-runs Ariv's single-LLM baseline prompt on his 3 MTSamples notes (3889, 1295, 184)
  2. Polishes each baseline output with v1 (current polish()) and v3 (week4/m5_polish_v3.py prompt)
  3. Scores readability, and checks which numbers + dose frequencies from the ORIGINAL note survive

Run from the repo root, with Ollama open:   python week4/m5_mtsamples_check.py
Outputs: results/m5_mtsamples_runs.csv (all text) and results/m5_mtsamples_report.md (easy to read)
Model: DEFAULT_MODEL (gemma2:2b). Ariv's baseline used qwen3.5:2b, so these baseline outputs are new.
"""
import re, time
import pandas as pd
import textstat as ts
from clearmed.models import call_model, DEFAULT_MODEL
from clearmed.agents.readability import polish

# Ariv's baseline prompt (notebooks/04a_single_llm_baseline.ipynb)
BASE_SYSTEM = "You are a helpful medical assistant who explains clinical notes to patients."
BASE_PROMPT = "Explain this clinical note to the patient in plain language.\n\n"

# Same v3 prompt as week4/m5_polish_v3.py
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

NOTE_IDS = [3889, 1295, 184]   # discharge summary, clinic visit (SOAP), surgery report

# Dose-frequency abbreviations -> words a correct plain-language version should contain
FREQUENCIES = {
    r"\bq\.?\s?d\.?\b|\bdaily\b": r"once a day|every day|daily",
    r"\bb\.?i\.?d\.?\b": r"twice a day|two times a day|2 times a day",
    r"\bt\.?i\.?d\.?\b": r"three times a day|3 times a day",
    r"\bq\.?i\.?d\.?\b": r"four times a day|4 times a day",
    r"\bp\.?r\.?n\.?\b": r"as needed|when needed|if needed",
    r"\bq\.?\s?(\d+)\s?h": r"every \1 hours",
}

def strip_markdown(text):
    text = re.sub(r"[*#>`_]+", "", str(text))
    lines = [l.strip(" -•\t") for l in text.splitlines() if l.strip()]
    return " ".join(l if re.search(r"[.!?:]$", l) else l + "." for l in lines)

def note_numbers(note):
    """Numbers in the original note, minus list numbering like '1.  Pyelonephritis'."""
    note = re.sub(r"(^|,|\s)\d+\.\s{1,3}(?=[A-Za-z])", " ", note)
    return sorted(set(re.findall(r"\d+(?:\.\d+)?", note)), key=float)

def frequency_checks(note, text):
    """For each frequency abbreviation in the note: is its plain meaning (or the abbreviation) in text?"""
    results = []
    for abbr, plain in FREQUENCIES.items():
        for m in re.finditer(abbr, note, re.I):
            want = m.expand(plain) if m.groups() else plain
            ok = bool(re.search(want, text, re.I)) or bool(re.search(abbr, text, re.I))
            results.append((m.group(0).strip(), ok))
    return results

df = pd.read_csv("data/mtsamples.csv")
rows, report = [], ["# M5 · MTSamples check: do polished outputs keep the clinical facts?\n",
                    f"Model: `{DEFAULT_MODEL}` for baseline and polish. Numbers ignore list numbering.\n"]

for nid in NOTE_IDS:
    note, name = df.loc[nid, "transcription"], df.loc[nid, "sample_name"].strip()
    nums = note_numbers(note)
    print(f"\n== {nid} {name}  ({len(note.split())} words, numbers in note: {nums})")

    t = time.time(); base = call_model(BASE_SYSTEM, BASE_PROMPT + note, model=DEFAULT_MODEL)
    texts = {"baseline": (base, round(time.time() - t, 1))}
    t = time.time(); texts["v1"] = (polish(base), round(time.time() - t, 1))
    t = time.time(); texts["v3"] = (call_model(PROMPT_V3, f"DRAFT:\n{base}", model=DEFAULT_MODEL), round(time.time() - t, 1))

    report.append(f"\n## {nid} · {name}\nNumbers in the original note: {', '.join(nums) or 'none'}\n")
    for version, (text, secs) in texts.items():
        clean = strip_markdown(text)
        kept = [n for n in nums if re.search(rf"(?<![\d.]){re.escape(n)}(?![\d])", text)]
        freqs = frequency_checks(note, text)
        row = {"note_id": nid, "name": name, "version": version, "seconds": secs,
               "fk": ts.flesch_kincaid_grade(clean), "smog": ts.smog_index(clean),
               "words": ts.lexicon_count(clean),
               "numbers_kept": f"{len(kept)}/{len(nums)}",
               "numbers_lost": ", ".join(n for n in nums if n not in kept),
               "frequencies": "; ".join(f"{a}: {'kept' if ok else 'LOST'}" for a, ok in freqs) or "none in note",
               "text": text}
        rows.append(row)
        print(f"  {version:8s} FK {row['fk']:5.1f}  words {row['words']:4d}  numbers kept {row['numbers_kept']:6s} "
              f"lost [{row['numbers_lost']}]  freq: {row['frequencies']}  ({secs}s)")
        report.append(f"\n### {version}: FK {row['fk']:.1f}, {row['words']} words, numbers kept {row['numbers_kept']}"
                      f" (lost: {row['numbers_lost'] or 'none'}); frequencies: {row['frequencies']}\n\n{text}\n")

out = pd.DataFrame(rows)
out.to_csv("results/m5_mtsamples_runs.csv", index=False)
open("results/m5_mtsamples_report.md", "w").write("\n".join(report))
print("\nSummary (mean over the 3 notes):")
print(out.groupby("version")[["fk", "smog", "words", "seconds"]].mean().round(1).reindex(["baseline", "v1", "v3"]).to_string())
print("\nRead every output side by side in results/m5_mtsamples_report.md")
