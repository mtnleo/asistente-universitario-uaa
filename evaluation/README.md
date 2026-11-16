# Offline retrieval benchmark

The frozen `gold.json` contains the original ten development questions (seven PDF, three calendar) and their 11 labeled evidence units. The real local answer index retrieves up to 24 cosine-ranked chunks, deduplicates by PDF page or calendar record, and scores the first 3 or 5 evidence units. Precision divides by *k*; recall divides by the number of labels for that question. Metrics are macro-averaged.

| Backend | Chunk size / overlap | Chunks | Precision@3 | Recall@3 | Precision@5 | Recall@5 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| In memory (historical) | 100 / 15 | 707 | 20.0% | 60% | 12% | 60% |
| ChromaDB | 100 / 15 | 707 | 20.0% | 60% | 12% | 60% |
| In memory (historical) | 60 / 15 | 1,266 | 26.7% | 75% | 16% | 75% |
| ChromaDB | 60 / 15 | 1,266 | 26.7% | 75% | 18% | 85% |

At the unchanged 100/15 default, all ten top-five rankings matched the baseline. In the 60/15 experiment, Chroma ranked one labeled prerequisites page fifth instead of sixth. This development set does not justify changing the default or establish answer quality. Calendar browsing, model tool selection, answers, and actions were not evaluated.

## Reproduce

Use the project Python 3.12 environment and install `requirements-prototype.txt`. The pinned MiniLM/tokenizer revision and original OCR outputs must already be cached under `.cache-prototype/`. The benchmark uses no Gemini, bookings, network calls, or OCR regeneration. It writes separate benchmark indexes, not the chat's answer index.

```sh
run_dir=$(mktemp -d)
.venv/bin/python evaluation/evaluate_chroma.py --index-dir "$run_dir/indexes" --output "$run_dir/cold.json"
.venv/bin/python evaluation/evaluate_chroma.py --index-dir "$run_dir/indexes" --output "$run_dir/warm.json" --expect-reuse
cmp "$run_dir/cold.json" "$run_dir/warm.json"
```

The warm process aborts if the production embedding provider tries to re-embed documents. `chroma_results.json` records per-question results, source and OCR hashes, and software versions.
