"""Latency logging (owner: M4) — time one function call and append a row to results/latency_log.csv.

Usage:
    from clearmed.timing import timed
    from clearmed.agents import refiner

    fixed = timed(refiner.refine, draft, verdict, model="ollama/qwen3.5:2b", notes="furosemide test")

Each call writes one row:
    timestamp, file, step, function, model, seconds, status, notes

- file:     the file the function lives in (e.g. refiner.py)
- step:     m1-m5, from the agent module (extractor=m1 ... readability=m5), or pass step= yourself
- model:    the model= kwarg if given, else the function's default model
- status:   "ok", or "error: <Type>" if the call raised (the error is still re-raised)

Nothing here changes any agent. It only wraps a call, so it works on anyone's function.
"""
from __future__ import annotations

import csv
import inspect
import os
import time
from datetime import datetime

LOG_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "results", "latency_log.csv")
COLUMNS = ["timestamp", "file", "step", "function", "model", "seconds", "status", "notes"]

# Agent module -> team step, so the log can be grouped per person.
STEPS = {
    "extractor": "m1",
    "simplifier": "m2",
    "verifier": "m3",
    "refiner": "m4",
    "readability": "m5",
}


def _step_for(func) -> str:
    module = getattr(func, "__module__", "") or ""
    return STEPS.get(module.rsplit(".", 1)[-1], "")


def _model_for(func, kwargs) -> str:
    if "model" in kwargs:
        return str(kwargs["model"])
    try:
        default = inspect.signature(func).parameters["model"].default
        return "" if default is inspect.Parameter.empty else str(default)
    except (KeyError, TypeError, ValueError):
        return ""


def _file_for(func) -> str:
    try:
        return os.path.basename(inspect.getsourcefile(func) or "")
    except TypeError:
        return ""


def log_latency(row: dict, path: str = LOG_PATH) -> None:
    """Append one row to the latency CSV, writing the header if the file is new."""
    path = os.path.abspath(path)
    is_new = not os.path.exists(path) or os.path.getsize(path) == 0
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        if is_new:
            writer.writeheader()
        writer.writerow({c: row.get(c, "") for c in COLUMNS})


def timed(func, *args, step: str | None = None, notes: str = "", log_path: str = LOG_PATH, **kwargs):
    """Run func(*args, **kwargs), log how many seconds it took, and return its result."""
    status = "ok"
    start = time.perf_counter()
    try:
        return func(*args, **kwargs)
    except Exception as e:
        status = f"error: {type(e).__name__}"
        raise
    finally:
        seconds = round(time.perf_counter() - start, 2)
        log_latency(
            {
                "timestamp": datetime.now().isoformat(timespec="seconds"),
                "file": _file_for(func),
                "step": step if step is not None else _step_for(func),
                "function": getattr(func, "__name__", str(func)),
                "model": _model_for(func, kwargs),
                "seconds": seconds,
                "status": status,
                "notes": notes,
            },
            log_path,
        )
