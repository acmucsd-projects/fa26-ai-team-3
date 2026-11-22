"""Refiner agent (owner: M4) — fix only what the Verifier flagged. No free rewriting.

Owner TODO: keep edits minimal and localized, design the bounded loop, confirm it converges
within 2 passes on the gold set.

How refine() works:
  1. Parse the Verifier's verdict (a JSON string, maybe wrapped in ```json fences) into a dict.
  2. If there is nothing to fix (faithful, or no claims/omissions listed), return the draft as is.
     No model call, so a faithful draft can never get changed by accident.
  3. Unsupported claims, one sentence at a time: blank the flagged phrase out ("___") and ask the
     model to fill the blank from the source facts (e.g. "twice a day" -> "daily"). The model only
     sees that one sentence, and its reply is only accepted if everything around the blank comes
     back unchanged. So the wrong phrase is gone by construction and the rest of the draft stays
     word-for-word the same. (Asking a 2B model to "fix X, change nothing else" doesn't work: at
     temperature 0 it copies the text back unchanged, and on a 400-word draft it retypes it all.)
     The model only gets the source facts that share a word with that sentence (_relevant), so it
     can't stuff unrelated facts into the blank.
  4. Omissions: short draft (<= SHORT_DRAFT_WORDS) -> model works the fact into the draft;
     long draft -> model writes one plain sentence with the fact, added at the end.
  5. Clean each reply (drop <think> blocks, code fences, "Corrected draft:" labels, echoed prompt).
     Reject anything that fails the checks above or is much longer than what it replaces; the
     original text is kept and the Verifier <-> Refiner loop gets another try.
  6. changes(before, after) lists every word-level edit, to check nothing else got changed.
"""
from __future__ import annotations

import difflib
import json
import re

from ..models import DEFAULT_MODEL, call_model

SHORT_DRAFT_WORDS = 120  # above this, missing facts are added as a new sentence instead of worked in
BLANK = "___"

PROMPT = (
    "You fix a patient-friendly DRAFT. The VERDICT lists exactly what is wrong with it.\n"
    "Rules:\n"
    "1. BLANK: the ___ in DRAFT replaced wrong words. Fill each ___ with the correct words from "
    "SOURCE FACTS. If nothing fits, remove the ___ and fix the grammar around it.\n"
    "2. MISSING: add that fact in plain words inside the sentence it belongs with. "
    "If DRAFT is empty, write one short plain sentence that states the fact.\n"
    "3. Change nothing else. Keep every other word, and formatting like ** or *, exactly the same.\n"
    "Return only the corrected draft. No labels, notes, or explanations.\n\n"
    "Example:\n"
    "DRAFT: Take your water pill ___.\n"
    "VERDICT: BLANK: fill the ___\nMISSING: dose is 40 mg\nSOURCE FACTS: Furosemide 40 mg daily.\n"
    "Answer: Take your water pill, 40 mg, daily."
)

# A sentence = text up to . ! or ? followed by a space/end, or up to a line break.
# "2.29" and "mg/dL." mid-line don't split, because the period isn't followed by a space.
_SENTENCE = re.compile(r"[^\n]*?(?:[.!?]+[\"')\]*]*(?=\s|$)|(?=\n)|$)")


def parse_verdict(verdict) -> dict:
    """Turn the Verifier's output into a dict. Returns {} if it can't be read as JSON."""
    if isinstance(verdict, dict):
        return verdict
    text = re.sub(r"<think>.*?</think>", "", str(verdict), flags=re.DOTALL)
    match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if not match:
        return {}
    try:
        parsed = json.loads(match.group(0))
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _as_list(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value] if value.strip() else []
    return [str(v) for v in value if str(v).strip()]


def clean_output(text: str) -> str:
    """Strip the extras small models add around the answer."""
    text = re.sub(r"<think>.*?</think>", "", text or "", flags=re.DOTALL).strip()
    fence = re.fullmatch(r"```[a-zA-Z]*\n?(.*?)\n?```", text, flags=re.DOTALL)
    if fence:
        text = fence.group(1).strip()
    text = re.sub(r"^(corrected draft|corrected|draft|output|answer)\s*:\s*", "", text, flags=re.IGNORECASE).strip()
    # Small models sometimes echo the prompt back ("VERDICT: ... SOURCE FACTS: <whole source>").
    # Keep only what comes before the first echoed label.
    text = re.split(r"\b(?:VERDICT|SOURCE FACTS|DRAFT)\s*:", text)[0].strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in "\"'“”":
        text = text[1:-1].strip()
    return text


def changes(before: str, after: str) -> list[tuple[str, str, str]]:
    """Word-level edits from `before` to `after`, as (op, old, new). Empty list = unchanged."""
    a, b = before.split(), after.split()
    out = []
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(a=a, b=b, autojunk=False).get_opcodes():
        if op != "equal":
            out.append((op, " ".join(a[i1:i2]), " ".join(b[j1:j2])))
    return out


def _too_long(old: str, new: str) -> bool:
    """A real fix swaps or adds a few words. Much longer = the model rewrote or padded it."""
    return len(new.split()) > 2 * len(old.split()) + 15


def _with_source(text: str, atoms: str) -> str:
    return text + (f"\nSOURCE FACTS: {atoms}" if atoms else "")


_STOP = {"the", "and", "for", "with", "your", "you", "are", "was", "were", "this", "that", "from",
         "have", "has", "not", "but", "can", "may", "will", "which", "their", "they", "its", "into"}


def _words(text: str) -> set[str]:
    """Content words, for matching a sentence to the source facts it's about ("40" counts, "a" doesn't)."""
    return {w for w in re.findall(r"[a-z0-9]+(?:\.[0-9]+)?", text.lower())
            if w not in _STOP and (len(w) >= 3 or any(ch.isdigit() for ch in w))}


def _relevant(atoms: str, sentence: str) -> str:
    """Only the source sentences that share a content word with `sentence`.

    Given every fact, a small model stuffs unrelated ones into the blank ("40 mg ___" ->
    "40 mg daily, with potassium 3.1 (low)"). If nothing overlaps, keep all the facts.
    """
    if not atoms:
        return atoms
    near = _words(sentence)
    facts = [m.group().strip() for m in _SENTENCE.finditer(atoms) if m.group().strip()]
    keep = [f for f in facts if _words(f) & near]
    return " ".join(keep) if keep else atoms


def _call(draft: str, verdict: str, model: str) -> str:
    return call_model(PROMPT, f"DRAFT:\n{draft}\n\nVERDICT:\n{verdict}", model=model)  # dont change, for free / local ollama models to avoid api keys


MAX_FILL_WORDS = 12


def _fills(masked: str, fixed: str) -> list[str] | None:
    """What the model wrote in each blank, or None if it changed anything outside the blanks.

    The text around the blanks must come back in order with nothing added before, between, or
    after it, and each fill must be short and not start a new sentence.
    """
    parts = [p.strip() for p in masked.split(BLANK)]
    fills, pos = [], 0
    for i, part in enumerate(parts):
        if part:
            j = fixed.find(part, pos)
            if j < 0:
                return None
            gap = fixed[pos:j].strip()
        else:
            j, gap = pos, ""
        if i == len(parts) - 1 and part and i > 0:
            # The last piece must END the reply. Matching its first occurrence breaks on fills
            # with punctuation: for "... ___." a fill like "3.1 (low)" would match the "." in "3.1".
            end = fixed.rstrip()
            if not end.endswith(part) or len(end) - len(part) < pos:
                return None
            j = len(end) - len(part)
            gap = fixed[pos:j].strip()
        if i == 0:
            if gap:
                return None  # text added before the sentence
        else:
            fills.append(gap)
        pos = j + len(part)
    if parts[-1] and fixed[pos:].strip():
        return None  # text added after the sentence (e.g. a copied extra sentence)
    if not parts[-1]:
        fills[-1] = (fills[-1] + " " + fixed[pos:]).strip()
    cleaned = []
    for f in fills:
        f = f.strip().strip("*").strip()  # models like to **bold** what they fill in
        if len(f.split()) > MAX_FILL_WORDS or re.search(r"[.!?]\s+\S", f):
            return None
        cleaned.append(f)
    return cleaned


def _only_additions(before: str, after: str) -> bool:
    """True if `after` only adds words to `before` (small 1-3 word swaps like "pill" -> "pill," allowed)."""
    return all(op == "insert" or (op == "replace" and len(old.split()) <= 3) for op, old, _ in changes(before, after))


def _fix_claims(draft: str, claims: list[str], atoms: str, model: str) -> str:
    """Blank out each flagged phrase, sentence by sentence, and let the model fill the blanks."""
    spans = [(m.start(), m.end()) for m in _SENTENCE.finditer(draft) if m.group().strip()]
    edits = []  # (start, end, new text)
    for start, end in spans:
        sentence = draft[start:end]
        here = [c for c in claims if c.lower() in sentence.lower()]
        if not here:
            continue
        lead = sentence[: len(sentence) - len(sentence.lstrip())]
        masked = sentence.strip()
        for c in here:
            masked = re.sub(re.escape(c), BLANK, masked, flags=re.IGNORECASE)
        # Don't show the model the wrong words: when it sees them, it just puts them back.
        issues = "BLANK: fill the ___"
        reply = clean_output(_call(masked, _with_source(issues, _relevant(atoms, masked)), model))
        fills = _fills(masked, reply) if reply and BLANK not in reply else None
        if fills is None or any(c.lower() in f.lower() for f in fills for c in here):
            continue  # no clean fill: keep the sentence; the Verifier flags it again next pass
        # Rebuild the sentence from the ORIGINAL text + the fills only, so nothing else can change.
        pieces = masked.split(BLANK)
        rebuilt = pieces[0] + "".join(f + p for f, p in zip(fills, pieces[1:]))
        rebuilt = re.sub(r"[ \t]{2,}", " ", rebuilt)  # an empty fill (deleted phrase) leaves a double space
        rebuilt = re.sub(r"\s+([.,;:!?])", r"\1", rebuilt) if any(not f for f in fills) else rebuilt
        edits.append((start, end, lead + rebuilt))
    for start, end, new in sorted(edits, reverse=True):  # back to front so offsets stay valid
        draft = draft[:start] + new + draft[end:]
    return draft


def refine(draft: str, verdict, model: str = DEFAULT_MODEL, *, atoms: str = "") -> str:
    """Return a corrected draft addressing the issues in `verdict`.

    `atoms` (optional) = the source facts. Without them the Refiner can only delete a wrong claim
    or guess the replacement, not look up the right one.
    """
    v = parse_verdict(verdict)
    unsupported = _as_list(v.get("unsupported_claims"))
    omissions = _as_list(v.get("omissions"))

    if v and not unsupported and not omissions:
        return draft  # nothing flagged -> nothing to fix

    if not v:  # unreadable verdict: pass it through as-is on the whole draft
        fixed = clean_output(_call(draft, _with_source(str(verdict), atoms), model))
        return draft if not fixed or _too_long(draft, fixed) else fixed

    out = draft
    if unsupported:
        located = [c for c in unsupported if c.lower() in draft.lower()]
        out = _fix_claims(out, located, atoms, model)
        # A claim that isn't word-for-word in the draft (paraphrased) can't be blanked out;
        # treat it like an omission: the model gets it as a note with the source facts.
        omissions = omissions + [f'the draft wrongly says "{c}"; state the correct fact' for c in unsupported if c not in located]

    if omissions:
        issues = _with_source("\n".join(f"MISSING: {o}" for o in omissions), atoms)
        if len(out.split()) <= SHORT_DRAFT_WORDS:
            fixed = clean_output(_call(out, issues, model))
            if fixed and not _too_long(out, fixed) and _only_additions(out, fixed):
                out = fixed
        else:
            added = clean_output(_call("", issues, model))
            if added and len(added.split()) <= 25 * len(omissions):
                out = out.rstrip() + "\n\n" + added
    return out
