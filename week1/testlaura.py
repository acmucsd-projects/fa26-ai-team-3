"""Laura's Week 1 Ollama test — a mini ClearMed-style rewrite + self-check."""
import ollama

MODEL = "qwen3"  # swap to "qwen3:1.7b" if your laptop is low on RAM

clinical_text = (
    "Pt discharged on metoprolol 25 mg PO BID. Hold if HR < 60. "
    "F/u w/ cardiology in 2 wks. Return to ED for CP or SOB."
)

try:
    # Step 1: simplify (like the Simplifier agent)
    simple = ollama.chat(
        model=MODEL,
        messages=[
            {"role": "system", "content": "Rewrite clinical text at a 6th-grade reading level. "
                                          "Do not add any facts that are not in the original."},
            {"role": "user", "content": clinical_text},
        ],
    )["message"]["content"]
    print("🩺 Original:\n", clinical_text, "\n")
    print("✏️  Simplified:\n", simple, "\n")

    # Step 2: check it against the source (like the Verifier agent)
    check = ollama.chat(
        model=MODEL,
        messages=[
            {"role": "system", "content": "For each sentence in the rewrite, say SUPPORTED or "
                                          "UNSUPPORTED by the original, with a short reason."},
            {"role": "user", "content": f"ORIGINAL:\n{clinical_text}\n\nREWRITE:\n{simple}"},
        ],
    )["message"]["content"]
    print("🔍 Verifier check:\n", check)

except Exception as e:
    print(f"❌ Error connecting to Ollama: {e}")
    print("Make sure the Ollama app is running in the background!")
