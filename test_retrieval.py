import json

from clearmed.retrieval import build_index, retrieve


# Step 1: Open our existing glossary.
with open("data/m2/m2-glossary.json", "r") as file:
    glossary = json.load(file)


# Step 2: Convert each glossary entry into text.
docs = []

for entry in glossary:
    term = entry["term"]
    definition = entry["definition"]

    document = f"{term}: {definition}"
    docs.append(document)


# Step 3: Build our ChromaDB index.
build_index(docs)

print(f"Successfully indexed {len(docs)} glossary entries!")


# Step 4: Search for a medical concept.
query = "high blood potassium"

results = retrieve(query, k=3)

print(f"\nSearch query: {query}")
print("\nTop 3 results:")

for i, result in enumerate(results, start=1):
    print(f"{i}. {result}")
