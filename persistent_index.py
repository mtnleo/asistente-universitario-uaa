"""Local Chroma storage for answer-eligible evidence and precomputed vectors."""

from collections import Counter
import hashlib
import json
from pathlib import Path


COLLECTION = "ia2_answer_chunks"
SCHEMA = 2


class StaleIndexError(RuntimeError):
    """A different local process replaced the index held by this process."""


def stable_digest(value):
    return hashlib.sha256(json.dumps(
        value, sort_keys=True, ensure_ascii=False, separators=(",", ":"),
    ).encode("utf-8")).hexdigest()


def evidence_id(metadata):
    return stable_digest([metadata["source"], metadata.get("record_id") or metadata["page"]])


class PersistentAnswerIndex:
    def __init__(self, path, pages, embeddings, make_chunks, page_metadata, config, manifest):
        import fcntl
        import chromadb
        from chromadb.config import Settings
        from chromadb.errors import NotFoundError

        self.embeddings = embeddings
        eligible = [p for p in pages if p.get("cloud_allowed") is True]
        self.metadata = {evidence_id(p): page_metadata(p) for p in eligible}
        if len(self.metadata) != len(eligible):
            raise ValueError("Duplicate answer evidence identity.")
        fingerprint = stable_digest({
            "schema": SCHEMA, "distance": "cosine", "config": config,
            "sources": manifest, "pages": eligible,
        })
        path = Path(path).resolve()
        path.mkdir(parents=True, exist_ok=True, mode=0o700)
        # Serialize first use and replacement across local CLI/web processes.
        # Never reuse an interrupted build (no final metadata) or a partial one.
        with (path / ".build.lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            client = chromadb.PersistentClient(
                path=str(path),
                settings=Settings(anonymized_telemetry=False,
                                  chroma_api_impl="chromadb.api.rust.RustBindingsAPI",
                                  chroma_otel_collection_endpoint="", chroma_otel_granularity="none"),
            )
            try:
                collection = client.get_collection(COLLECTION, embedding_function=None)
            except NotFoundError:
                collection = None
            saved = collection.metadata if collection is not None else None
            self.reused = (
                saved is not None and saved.get("fingerprint") == fingerprint
                and isinstance(saved.get("chunks"), int)
                and collection.count() == saved["chunks"] > 0
            )
            if not self.reused:
                if collection is not None:
                    client.delete_collection(COLLECTION)
                chunks = make_chunks(eligible)
                if not chunks:
                    raise ValueError("No answer-eligible chunks; the old index was invalidated.")
                collection = client.create_collection(
                    COLLECTION, embedding_function=None,
                    configuration={"hnsw": {"space": "cosine"}},
                )
                positions = Counter()
                batch_size = client.get_max_batch_size()
                for start in range(0, len(chunks), batch_size):
                    batch = chunks[start:start + batch_size]
                    ids, metadatas = [], []
                    for chunk in batch:
                        identity = evidence_id(chunk.metadata)
                        if identity not in self.metadata or chunk.metadata.get("cloud_allowed") is not True:
                            raise ValueError("A restricted chunk cannot enter the answer index.")
                        ids.append(f"{identity}-{positions[identity]}")
                        metadatas.append({
                            "evidence_id": identity, "cloud_allowed": True,
                            **{key: chunk.metadata[key] for key in
                               ("source", "page", "record_id", "kind", "extraction")
                               if chunk.metadata.get(key) is not None},
                        })
                        positions[identity] += 1
                    texts = [chunk.page_content for chunk in batch]
                    collection.add(ids=ids, documents=texts, metadatas=metadatas,
                                   embeddings=embeddings.embed_documents(texts))
                if collection.count() != len(chunks):
                    raise ValueError("Incomplete Chroma index; it will not be reused.")
                collection.modify(metadata={"fingerprint": fingerprint, "chunks": len(chunks)})
            self.collection = collection

    def similarity_search_with_score(self, query, k=4, filter=None):
        from chromadb.errors import NotFoundError
        from langchain_core.documents import Document

        try:
            hits = self.collection.query(
                query_embeddings=[self.embeddings.embed_query(query)], n_results=k,
                where={"cloud_allowed": True}, include=["documents", "metadatas", "distances"],
            )
        except NotFoundError:
            raise StaleIndexError("The local index was replaced. Restart the assistant.") from None
        results = []
        for text, stored, distance in zip(
            hits["documents"][0], hits["metadatas"][0], hits["distances"][0], strict=True,
        ):
            # Rehydrate canonical provenance (including structured calendar evidence).
            # Stored flags never authorize evidence from the current corpus.
            metadata = self.metadata.get(stored["evidence_id"])
            if metadata is None or metadata.get("cloud_allowed") is not True:
                continue
            document = Document(page_content=text, metadata=metadata)
            if filter is None or filter(document):
                results.append((document, 1 - distance))  # Cosine similarity, not confidence.
        return results
