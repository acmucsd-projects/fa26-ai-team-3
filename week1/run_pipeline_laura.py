"""Laura: first end-to-end run of the full 5-agent ClearMed pipeline on one fake note."""
import time
from clearmed.pipeline import build_graph

note = (
    "Pt discharged on metoprolol 25 mg PO BID. Hold if HR < 60. "
    "F/u w/ cardiology in 2 wks. Return to ED for CP or SOB."
)

start = time.time()
result = build_graph().invoke({"source": note})

for key in ["atoms", "draft", "verdict", "refine_passes", "final"]:
    print(f"\n===== {key.upper()} =====\n{result.get(key)}")
print(f"\n⏱️  Total time: {time.time() - start:.1f}s")
