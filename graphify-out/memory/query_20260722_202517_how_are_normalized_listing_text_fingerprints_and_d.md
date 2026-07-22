---
type: "query"
date: "2026-07-22T20:25:17.345108+00:00"
question: "How are normalized listing text fingerprints and duplicate-description risk signals connected to the listing import pipeline and its tests?"
contributor: "graphify"
source_nodes: ["listing_text_similarity()", "listing_text_fingerprint()"]
---

# Q: How are normalized listing text fingerprints and duplicate-description risk signals connected to the listing import pipeline and its tests?

## Answer

The structural graph exposes listing_text_fingerprint and listing_text_similarity in duplicates.py, but the depth-2 traversal does not provide enough edges to prove their connection to the import service or integration test. That connection must be verified directly from source and test execution.

## Source Nodes

- listing_text_similarity()
- listing_text_fingerprint()