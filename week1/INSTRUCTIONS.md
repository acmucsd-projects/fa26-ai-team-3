# Week 1 — Setup

Done when `python week1/testnicole.py` prints a model response. All free, all local — no API keys.

1. **Install Ollama** from https://ollama.com/download, then **open the app** (it has to be
   running in the background).

2. **Make a venv** in the repo root:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate      # Windows: .venv\Scripts\activate
   ```
   Re-run the activate line in every new terminal — look for `(.venv)` in your prompt.

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   pip install -e .               # makes `import clearmed` work
   pip install ollama
   ```

4. **Pull a model:** `ollama pull qwen3` (a few GB). Low on RAM? Use `qwen3:1.7b`.

5. **Run it:** `python week1/testnicole.py`


**If it breaks:** `Error connecting to Ollama` → app isn't running. `No module named ...` →
venv not activated, or step 3 skipped. Anything else, post the error in the team chat.
