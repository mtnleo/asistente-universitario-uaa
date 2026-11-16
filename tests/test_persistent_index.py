"""Chroma regressions with deterministic local vectors and a fake answer model."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from langchain_core.documents import Document
from langchain_core.messages import AIMessage, ToolMessage
from pypdf import PdfWriter
from persistent_index import COLLECTION, PersistentAnswerIndex, StaleIndexError
import prototype_rag as rag
from rag_tools import answer_question


class Embeddings:
    def __init__(self, allow_documents=True):
        self.allow_documents = allow_documents
        self.encoded = []

    def embed_documents(self, texts):
        if not self.allow_documents:
            raise AssertionError("Warm process tried to embed corpus text.")
        self.encoded.extend(texts)
        return [self.embed_query(text) for text in texts]

    def embed_query(self, text):
        return [1.0, 0.0] if "private" in text else [0.0, 1.0]


class Tokenizer:
    def encode(self, text, **kwargs):
        return text.split()


class FakeChat:
    def __init__(self):
        self.evidence = None

    def bind_tools(self, tools, **kwargs):
        return self

    def invoke(self, messages):
        tool_output = next((msg.content for msg in messages if isinstance(msg, ToolMessage)), None)
        if tool_output is not None:
            self.evidence = tool_output
            return AIMessage(content="Answer from [S1].")
        return AIMessage(content="", tool_calls=[{
            "id": "search", "name": "search_documents", "args": {"query": "private material"},
        }])


def page(text, source="public.pdf", allowed=True):
    return {"source": source, "page": 1, "text": text, "cloud_allowed": allowed, "extraction": "pdf"}


def split(pages):
    return [Document(page_content=p["text"], metadata=rag.page_metadata(p)) for p in pages]


def open_index(path, pages, embeddings, *, manifest=None, config=None, chunks=split):
    return PersistentAnswerIndex(path, pages, embeddings, chunks, rag.page_metadata,
                                 config or {"revision": "model-v1"}, manifest)


def subprocess_probe(path, mode):
    changing = mode in {"edited", "revoked"}
    public = page("public edited" if changing else "public original")
    earlier_public = page("later private", "changed-access.pdf", allowed=mode != "revoked")
    unknown = page("unknown private", "unknown.pdf")
    del unknown["cloud_allowed"]
    pages = [public, earlier_public, page("always private", "manual_mp.pdf", False), unknown]
    embeddings = Embeddings(allow_documents=mode != "warm")
    store = open_index(path, pages, embeddings)
    chat = FakeChat()
    payload = answer_question(rag, chat, store, Tokenizer(), pages, "private material?")
    return {
        "reused": store.reused, "embedded": embeddings.encoded,
        "stored": sorted(store.collection.get(include=["documents"])["documents"]),
        "tool_evidence": chat.evidence, "sources": [item["text"] for item in payload["sources"]],
        "fingerprint": store.collection.metadata["fingerprint"],
        "ids": sorted(store.collection.get(include=[])["ids"]),
    }


class PersistentIndexTest(unittest.TestCase):
    def test_reopen_after_exit_and_invalidate_edits_and_revocation(self):
        with tempfile.TemporaryDirectory() as cache:
            def probe(mode):
                result = subprocess.run(
                    [sys.executable, str(Path(__file__).resolve()), cache, mode],
                    check=True, capture_output=True, text=True, timeout=45,
                    env={**os.environ, "CHROMA_API_IMPL": "chromadb.api.fastapi.FastAPI"},
                )
                return json.loads(result.stdout)

            cold = probe("cold")
            self.assertFalse(cold["reused"])
            self.assertCountEqual(cold["embedded"], ["public original", "later private"])
            self.assertTrue((Path(cache) / "chroma.sqlite3").is_file())
            warm = probe("warm")
            self.assertTrue(warm["reused"])
            self.assertEqual(warm["embedded"], [])
            self.assertEqual(warm["ids"], cold["ids"])
            self.assertEqual(warm["fingerprint"], cold["fingerprint"])
            self.assertEqual(warm["sources"], cold["sources"])
            edited = probe("edited")
            self.assertFalse(edited["reused"])
            self.assertNotEqual(edited["fingerprint"], cold["fingerprint"])
            self.assertIn("public edited", edited["stored"])
            self.assertNotIn("public original", edited["stored"])
            revoked = probe("revoked")
            self.assertFalse(revoked["reused"])
            self.assertNotEqual(revoked["fingerprint"], edited["fingerprint"])
            self.assertEqual(revoked["embedded"], ["public edited"])
            self.assertEqual(revoked["stored"], ["public edited"])
            self.assertEqual(revoked["sources"], ["public edited"])
            self.assertNotIn("later private", revoked["tool_evidence"])
            for result in (cold, warm, edited, revoked):
                for marker in ("always private", "unknown private"):
                    self.assertNotIn(marker, result["tool_evidence"])
                    self.assertNotIn(marker, result["stored"])
                    self.assertNotIn(marker, result["embedded"])

    def test_fingerprint_invalidates_config_and_source_bytes(self):
        with tempfile.TemporaryDirectory() as cache:
            pages = [page("same extracted text")]
            first = open_index(cache, pages, Embeddings(), manifest={"public.pdf": "original"})
            self.assertFalse(first.reused)
            changed = open_index(cache, pages, Embeddings(), manifest={"public.pdf": "updated"})
            self.assertFalse(changed.reused)
            self.assertNotEqual(first.collection.id, changed.collection.id)
            changed_model = open_index(cache, pages, Embeddings(), manifest={"public.pdf": "updated"},
                                       config={"revision": "model-v2"})
            self.assertFalse(changed_model.reused)
            self.assertNotEqual(changed.collection.id, changed_model.collection.id)
            with self.assertRaisesRegex(StaleIndexError, "Restart the assistant"):
                first.similarity_search_with_score("same evidence")

    def test_interrupted_build_cannot_be_reused(self):
        import chromadb
        from chromadb.config import Settings

        with tempfile.TemporaryDirectory() as cache:
            pages = [page("public evidence")]
            with self.assertRaisesRegex(AssertionError, "embed corpus"):
                open_index(cache, pages, Embeddings(allow_documents=False))
            retry = open_index(cache, pages, Embeddings())
            self.assertFalse(retry.reused)
            self.assertEqual(retry.collection.count(), 1)
            with self.assertRaisesRegex(ValueError, "No answer-eligible chunks"):
                open_index(cache, [page("now private", allowed=False)], Embeddings())
            client = chromadb.PersistentClient(path=cache, settings=Settings(anonymized_telemetry=False))
            self.assertNotIn(COLLECTION, [c.name for c in client.list_collections()])

    def test_restricted_pdf_alias_stays_restricted_even_if_seen_first(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(rag, "CORPUS", Path(folder)):
            original = rag.CORPUS / "manual_mp.pdf"
            writer = PdfWriter()
            writer.add_blank_page(width=72, height=72)
            writer.write(original)
            shutil.copyfile(original, rag.CORPUS / "a-alias.pdf")
            with patch.object(rag, "ocr_pages", return_value={"1": "private marker"}):
                pages, _ = rag.load_pages(["a-alias.pdf", "manual_mp.pdf"])
            self.assertEqual(len(pages), 1)
            self.assertIs(pages[0]["cloud_allowed"], False)


if __name__ == "__main__":
    print(json.dumps(subprocess_probe(*sys.argv[1:])))
