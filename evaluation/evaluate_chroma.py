#!/usr/bin/env python3
"""Compare the real offline Chroma answer index with the frozen IA2 benchmark."""

import argparse
import hashlib
from importlib.metadata import version
import json
import os
from pathlib import Path
from statistics import mean
import sys
from tempfile import TemporaryDirectory
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
GOLD_SHA256 = "1f8e7b5d5b22215c8cc49209521170ec073295f9992e1f2b38152429f46a4663"
BASELINE = {
    "100/15": {"chunks": 707, "p3": 0.20, "r3": 0.60, "p5": 0.12, "r5": 0.60},
    "60/15": {"chunks": 1266, "p3": 4 / 15, "r3": 0.75, "p5": 0.16, "r5": 0.75},
}


def evidence_key(metadata):
    return metadata["source"], metadata.get("record_id") or metadata["page"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--index-dir", type=Path, help="Keep benchmark indexes for a restart check.")
    parser.add_argument("--expect-reuse", action="store_true", help="Fail on any corpus re-embedding.")
    args = parser.parse_args()
    if args.expect_reuse and args.index_dir is None:
        parser.error("--expect-reuse requires --index-dir from a completed previous run.")
    os.environ.update(HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1", HF_HUB_DISABLE_TELEMETRY="1",
                      LANGSMITH_TRACING="false", LANGCHAIN_TRACING_V2="false",
                      TOKENIZERS_PARALLELISM="false")
    sys.path.insert(0, str(HERE.parent))
    import prototype_rag as rag
    import torch
    from langchain_huggingface import HuggingFaceEmbeddings

    torch.set_num_threads(3)
    gold_raw = (HERE / "gold.json").read_bytes()
    if hashlib.sha256(gold_raw).hexdigest() != GOLD_SHA256:
        raise ValueError("The original benchmark questions and labels must stay frozen.")
    questions = json.loads(gold_raw)["questions"]

    def cached_ocr(path, digest, numbers):
        file = rag.CACHE / "ocr" / f"{digest}.json"
        data = json.loads(file.read_text()) if file.is_file() else {}
        if any(not data.get(str(n), "").strip() for n in numbers):
            raise RuntimeError(f"Missing cached OCR for {path.name}; no fallback.")
        return data

    manifest = {}
    names = sorted(p.name for p in rag.CORPUS.glob("*.pdf") if p.name not in rag.LOCAL_ONLY_FILES)
    with patch.object(rag, "ocr_pages", cached_ocr):
        pdfs, report = rag.load_pages(names, manifest=manifest)
    if any(row.get("error_type") or row.get("failed_pages") or row.get("empty_pages") for row in report):
        raise RuntimeError("Incomplete PDF extraction; results would not match the frozen benchmark.")
    calendar, _ = rag.load_calendar_records(manifest=manifest)
    pages = pdfs + calendar
    allowed = {evidence_key(p) for p in pages if p.get("cloud_allowed") is True}
    if len(allowed) != len(pages):
        raise RuntimeError("Duplicate evidence identity or unexpected restricted page.")
    for question in questions:
        expected = {tuple(unit) for unit in question["gold"]}
        if not expected or not expected <= allowed:
            raise RuntimeError(f"Unanswerable or out-of-corpus label: {question['id']}.")

    results = {
        "gold_sha256": GOLD_SHA256, "embedding_model": rag.EMBEDDINGS,
        "embedding_revision": rag.EMBEDDING_REVISION,
        "software": {pkg: version(pkg) for pkg in (
            "chromadb", "torch", "langchain-core", "langchain-huggingface",
            "langchain-text-splitters", "sentence-transformers", "transformers",
            "tokenizers", "pypdf",
        )},
        "units": {"pdfs": len({p["source"] for p in pdfs}), "pdf_pages": len(pdfs),
                  "ocr_unverified": sum(p["extraction"] == "ocr_unverified" for p in pdfs),
                  "calendar_records": len(calendar), "questions": len(questions)},
        "indexed_source_sha256": {p["source"]: manifest[p["source"]] for p in pages},
        "duplicate_sources": {row["file"]: row["duplicate_of"] for row in report if "duplicate_of" in row},
        "ocr_cache_sha256": {row["file"]: hashlib.sha256(
            (rag.CACHE / "ocr" / f"{manifest[row['file']]}.json").read_bytes()
        ).hexdigest() for row in report if row.get("ocr_unverified_pages")},
        "protocol": "Fixed questions, top 24 cosine chunks, deduplicated by evidence unit; macro P/R@3 and @5.",
        "in_memory_baseline": BASELINE, "chroma": {},
    }

    with TemporaryDirectory(prefix="ia2-chroma-eval-") as temp:
        for size, overlap in ((100, 15), (60, 15)):
            path = (args.index_dir or Path(temp)) / f"{size}-{overlap}"
            build = dict(index_path=path, manifest=manifest, chunk_size=size, chunk_overlap=overlap)
            if args.expect_reuse:
                with patch.object(HuggingFaceEmbeddings, "embed_documents",
                                  side_effect=AssertionError("Warm run tried to embed the corpus.")):
                    store, tokenizer = rag.build_store(pages, **build)
                if not store.reused:
                    raise RuntimeError("The expected persisted Chroma collection was not reused.")
            else:
                store, tokenizer = rag.build_store(pages, **build)
            rows = []
            for question in questions:
                query = question["question"]
                if len(tokenizer.encode(query, add_special_tokens=True)) > rag.EMBEDDING_MAX_TOKENS:
                    raise ValueError(f"Question exceeds model window: {question['id']}.")
                chunks = store.similarity_search_with_score(query, k=24)
                ranked = list(dict.fromkeys(evidence_key(doc.metadata) for doc, _ in chunks))
                want = {tuple(unit) for unit in question["gold"]}
                rows.append({"id": question["id"], "top5": ranked[:5], "labels": len(want),
                             "hits3": len(set(ranked[:3]) & want), "hits5": len(set(ranked[:5]) & want)})
            stats = {f"p{k}": mean(row[f"hits{k}"] / k for row in rows) for k in (3, 5)}
            stats.update({f"r{k}": mean(row[f"hits{k}"] / row["labels"] for row in rows) for k in (3, 5)})
            results["chroma"][f"{size}/{overlap}"] = {
                "chunks": store.collection.count(), **stats, "queries": rows,
            }
    args.output.write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
