# UAA University Assistant

**Throwaway local RAG prototype, not a finished university service.** The experiment asks: can passages extracted from our university PDFs support useful answers with inspectable page citations? The terminal interface can be replaced later; model, corpus and hosting choices are provisional.

For team onboarding, current decisions, assignment gaps and next tasks, read [Project status and team handoff](docs/PROJECT_STATUS.md).

## Quick start

Use Python 3.12. From this repository:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-prototype.txt
.venv/bin/python prototype_rag.py --inspect
```

Inspect reports PDF coverage without downloading models or contacting Gemini. Then try local retrieval, without any API key:

```sh
.venv/bin/python prototype_rag.py --retrieve-only --question "¿Qué establece el reglamento sobre la regularidad?"
```

The first retrieval downloads a multilingual embedding model (roughly 470 MB plus dependencies; local disk/network required). Its weights are cached in ignored `.cache-prototype/`. Embeddings and the scratch vector index run locally on CPU. The index is rebuilt per process, not saved.

### Enable answers with your own free-tier key

1. If `.env` does not exist, copy `.env.example` to `.env`. Edit it locally; never paste the key into chat or Git.
2. Set `GOOGLE_API_KEY` to your existing Gemini Developer API key. Confirm its project is **Free**, without Cloud Billing enabled; the Google One student plan is separate from API billing.
3. Read the comments and set `FREE_TIER_CONFIRMED=true` and `ALLOW_DOCUMENT_SNIPPETS=true` only if both are true. They are manual confirmations, not a technical billing lock.
4. Start the terminal chat:

```sh
.venv/bin/python prototype_rag.py
```

Type a question or `/quit`. For a single answer:

```sh
.venv/bin/python prototype_rag.py --question "¿Qué documentación permite conocer el plan de Licenciatura en Informática?"
```

Only the current question and up to four retrieved source pages (8000 characters per page maximum) are sent to Gemini; no full PDF upload, conversation history, n8n call, web search, or booking occurs. The answer follows the question's language. Retrieved passages, similarity scores, filenames and human page numbers are shown for inspection.

## Cost and privacy boundaries

- Uses only `gemini-3.1-flash-lite`, provisionally listed with free Standard input/output on the [official pricing page](https://ai.google.dev/gemini-api/docs/pricing). It worked in the initial trial; future availability and shared quotas are not guaranteed. No alternative-model fallback or paid features are enabled.
- Do not enable API billing. An API key does not let this script verify or enforce Google billing status. Stop using it if that project later becomes paid.
- Quotas are shared with your n8n automations in the same project. API errors, including exhausted quota, stop the process without application-level retries.
- Free-service prompts and responses may be used by Google to improve products. Do not ask personal questions or send private student records, confidential material, or unreviewed screenshots. A private GitHub repo does not make API transmissions private. See [Google's terms](https://ai.google.dev/gemini-api/terms).
- The source teaching notebook contains an apparent credential and must not be imported unchanged. `.env`, notebook files and local model cache are ignored. No key is bundled here.

## What is covered

All actual `archivos_RAG/*.pdf` files are discovered at startup and indexed locally, skipping byte-identical duplicates. The current run covers **24 files / 23 unique PDFs / 149 pages**: 106 native-text pages and 43 pages with **unverified OCR**. No selected page remained empty or failed, but this is not a quality guarantee. Blank-extraction pages receive local macOS Vision OCR cached by original PDF SHA256 under ignored `.cache-prototype/ocr/`; source PDFs are never rewritten.

**Local-only documents:** `manual_descarga.pdf` and `manual_mp.pdf` contain screenshots with identity/account fields that have not been verified synthetic. Their 36 pages can be searched with `--retrieve-only`, but their text is blocked from Gemini. Answer-mode retrieval filters them out before top-k selection, and context formatting rejects local-only evidence as a final guard. Cloud answer scope is currently **21 unique PDFs / 113 pages**. The file gate is not automatic personal-data detection or redaction; review any new file before adding it and update `LOCAL_ONLY_FILES` when needed. Tables, OCR and document applicability still require review.

Inspect all PDFs:

```sh
.venv/bin/python prototype_rag.py --inspect
```

Inspect or retrieve from explicitly selected PDFs locally:

```sh
.venv/bin/python prototype_rag.py --retrieve-only --files CorrelativasLicInformatica.pdf --question "¿Qué correlativas se mencionan?"
```

Custom file lists remain local-only in this prototype. Inspection labels cloud eligibility and reports extraction/OCR coverage. An exact duplicate is skipped rather than indexed twice. Quick OCR requires macOS with Swift and Vision; no OCR dependencies are installed. It is not visually quality-validated. Markdown conversion is not implemented.

## How it works and what remains

`pypdf + local Vision OCR for blank pages → Documents (source/page/extraction) → token-aware chunks → local embeddings → vector search → source-page expansion → Gemini answer`

Chunks target 100 tokenizer tokens with 15-token overlap, below the embedding model's 128-token limit. Questions exceeding 128 tokens (including special tokens) are rejected before retrieval or sending to Gemini; shorten them instead of silently losing part of the question. There is no calibrated relevance cutoff: an unrelated question still retrieves nearest neighbors. Similarity is not confidence or measured Precision/Recall; the prompt asks the model to decline unsupported answers, but this is not a factuality or prompt-injection guarantee. Citations are model-generated and must be checked. No official-currentness or amendment resolution is implemented.

The four assignment deliverables remain: use-case/system-prompt/model design; Python/LangChain document RAG; LLM intent/date extraction and n8n Calendar/email actions; retrieval Precision/Recall experiments and a final architecture/results report. This prototype addresses only an initial slice of document Q&A. Career scope, authoritative corpus/versioning, actions, final storage and deployment remain open. An existing Pi5 runs n8n and is optional infrastructure; no connection is made here.

## Record the experiment

Try one supported question, one ambiguous question and one unrelated question. Record which retrieved passage supports each answer and any extraction errors. **Initial verdict:** three real Gemini questions succeeded with the earlier eight-file subset. Full-corpus local inspection/retrieval now runs without a new cloud call; OCR/factual review and measured evaluation remain pending. See [project status](docs/PROJECT_STATUS.md) before choosing the next task. Once the experiment is useful, absorb the validated pieces or delete the throwaway terminal shell rather than treating it as production.
