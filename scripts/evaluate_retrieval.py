"""Evaluate local MiniLM and MPNet glossary retrieval on 20 labeled queries."""
import json
from pathlib import Path

import chromadb
from chromadb.utils import embedding_functions

ROOT = Path(__file__).resolve().parents[1]
COLLECTION = "medlineplus_glossary"
K = 3

MODELS = {
    "MiniLM": "all-MiniLM-L6-v2",
    "MPNet": "all-mpnet-base-v2",
}

# (query, expected glossary term, query type)
TESTS = [
    ("Hyperkalemia", "Hyperkalemia", "exact"),
    ("Creatinine", "Creatinine", "exact"),
    ("Thyroiditis", "thyroiditis", "exact"),
    ("Meniscus tear", "Meniscus tear", "exact"),
    ("high blood potassium", "Hyperkalemia", "synonym"),
    ("abnormal heart rhythm", "Arrhythmias", "synonym"),
    ("uncontrolled urine leakage", "Urinary incontinence", "synonym"),
    ("too much sugar in the bloodstream", "hyperglycemia", "synonym"),
    ("diabetes-related kidney disease", "Diabetic nephropathy", "synonym"),
    ("blood sugar test after not eating", "fasting plasma glucose", "synonym"),
    ("overactive thyroid", "hyperthyroidism", "synonym"),
    ("surgery to remove the thyroid gland", "thyroidectomy", "synonym"),
    ("fluid-filled swelling behind the knee", "Popliteal cysts", "synonym"),
    ("joint cartilage wearing down", "Cartilage degeneration", "synonym"),
    ("high triglyceride levels", "hypertriglyceridemia", "synonym"),
    ("SUI", "Stress urinary incontinence (SUI)", "abbreviation"),
    ("IDDM", "IDDM", "abbreviation"),
    ("NIDDM", "NIDDM", "abbreviation"),
    ("TSH", "thyroid-stimulating hormone", "abbreviation"),
    ("MRI", "Magnetic resonance imaging", "abbreviation"),
]


def main():
    glossary = json.loads((ROOT / "data/m2/m2-glossary.json").read_text())
    docs = [f'{entry["term"]}: {entry["definition"]}' for entry in glossary]
    glossary_terms = {entry["term"].casefold() for entry in glossary}

    for query, expected, category in TESTS:
        if expected.casefold() not in glossary_terms:
            raise ValueError(f"Expected term not in glossary: {expected}")

    for model_label, model_name in MODELS.items():
        path = ROOT / "data" / "chroma_eval" / model_label.lower()
        client = chromadb.PersistentClient(path=str(path))
        names = {c if isinstance(c, str) else c.name for c in client.list_collections()}
        if COLLECTION in names:
            client.delete_collection(name=COLLECTION)

        embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name=model_name
        )
        collection = client.create_collection(
            name=COLLECTION, embedding_function=embedding_fn
        )
        collection.add(
            ids=[f"glossary-{i}" for i in range(len(docs))], documents=docs
        )

        top1 = topk = 0
        misses = []
        for query, expected, category in TESTS:
            results = collection.query(
                query_texts=[query], n_results=K, include=["documents"]
            )
            returned = [doc.split(": ", 1)[0].casefold()
                        for doc in (results["documents"][0] or [])]
            target = expected.casefold()
            top1 += target in returned[:1]
            topk += target in returned[:K]
            if target not in returned[:1]:
                print(f"\nTop-1 miss for {model_label}:")
                print(f"Query: {query}")
                print(f"Expected: {expected}")
                print(f"Retrieved: {returned}")
            if target not in returned[:K]:
                misses.append((query, expected, category, returned))

        total = len(TESTS)
        print(f"\n{model_label} ({model_name})")
        print(f"Top-1: {top1}/{total} = {100 * top1 / total:.1f}%")
        print(f"Top-{K}: {topk}/{total} = {100 * topk / total:.1f}%")
        print(f"Top-{K} misses: {len(misses)}")
        for query, expected, category, returned in misses:
            print(f"  [{category}] {query!r} | expected={expected!r} | got={returned}")


if __name__ == "__main__":
    main()
