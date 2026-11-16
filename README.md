# UAA University Assistant

**Throwaway local RAG prototype, not a finished university service.** The experiment asks: can passages extracted from our university PDFs support useful answers with inspectable page citations? A basic local web interface is included; model, corpus and hosting choices are provisional.

For team onboarding, current decisions, assignment gaps and next tasks, read [Project status and team handoff](docs/PROJECT_STATUS.md).

## Final submission

- [Final project report (PDF, Spanish)](docs/IA2-Informe-Final.pdf)
- [ChromaDB evaluation and reproduction instructions](evaluation/README.md)
- [Historical in-memory retrieval experiment](evaluation/ia2-evaluacion-rag.zip)
- [Historical Gemini temperature experiment](evaluation/ia2-temperatura-gemini.zip)

The report covers the local prototype and includes screenshots of the chat and automation. Reviewing the code does not require access to the n8n instance.

## Quick start

Double-click **Abrir asistente.command** to open the local chat at `http://127.0.0.1:8765` once the environment below is installed. Keep its Terminal window open. Opening the page does not call Gemini; submitting a question does.


Use Python 3.12. From this repository:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-prototype.txt
.venv/bin/python prototype_rag.py --inspect
```

Inspect reports PDF and curated-calendar coverage without downloading models or contacting Gemini. Calendar-only inspection uses the Python standard library. Run the full offline regression suite with the installed virtual environment:

```sh
python3 -B prototype_rag.py --calendar-only --inspect
.venv/bin/python -B -m unittest discover -s tests -v
```

The curated 2026 calendar contains 102 visually reviewed event records, explicit source/page references and unresolved date variants. See [calendar curation and limits](docs/CALENDAR_CURATION.md). Then try local retrieval, without any API key:

```sh
.venv/bin/python prototype_rag.py --retrieve-only --question "¿Qué establece el reglamento sobre la regularidad?"
```

The first retrieval downloads the pinned multilingual MiniLM weights (roughly 470 MB plus dependencies; local disk/network required). The weights are cached in ignored `.cache-prototype/` and run locally on CPU.

- **Answer mode (chat or CLI):** ChromaDB stores the answer-eligible chunks and cosine index in `.cache-prototype/chroma-answers/`. On restart, unchanged input reuses the saved corpus vectors; each new semantic query still needs its own embedding. Changed PDFs, extracted/OCR evidence, curated calendar, privacy settings, or index configuration trigger a rebuild.
- **`--retrieve-only`:** local inspection uses a separate scratch index in memory. It can include restricted documents without writing them into the answer index.

Close other assistant instances before editing/reindexing the corpus, and restart the assistant to load changes. This is a single-user local cache, not a shared service or an access-control boundary. If its files are damaged, close the assistant and remove only `.cache-prototype/chroma-answers/` to rebuild.

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

The current question starts a bounded evidence-tool conversation with Gemini: up to **three model calls**, no retries or paid/model fallback. Gemini chooses a concise document search or reads the complete calendar (optionally filtered by date/year), and can refine once before answering. Broad calendar lists use calendar browsing, **not a fixed top-k**. Up to three tools per retrieval round execute, with a cumulative **160,000-character evidence budget**. Incomplete coverage and PDF-page truncation are disclosed; output is capped at 4096 tokens and may still be partial. More model calls consume more of the same shared Free-tier quota, not a new service.

Only cloud-eligible evidence is transmitted. Sources have stable IDs for that question and are displayed below the answer. No whole-PDF upload, general conversation history or web search occurs. The web chat also supports explicitly confirmed event actions (see below); the CLI remains document-only. Raw calendar PDFs and manuals retain their local-only gate. The user reported four independently chosen calendar/document questions working after the tool-based redesign. This is a user-reported smoke check, not comprehensive validation or measured retrieval quality; the offline test verifies tool orchestration, not model judgment.

## Optional Calendar/email actions in the local web chat

The chat can prepare an event from your request, clarify missing title/start/end/email,
and show all fields before **Confirmar y enviar**. No default duration or service catalog
is assumed. Relative dates use the server clock in Argentina. Document Q&A is unchanged.

1. Obtain the existing n8n webhook Header Auth key securely from its owner. Do not paste it into chat.
2. Run `.venv/bin/python configurar_n8n.py` locally. Its hidden prompt creates ignored,
   owner-only `.env.n8n`; it never sends an action or reads an existing secret.
3. Restart the chat, request your event, review title, dates, offset and recipient, then
   confirm or cancel with the buttons. Until the key is configured, actions fail closed.

The configuration uses `N8N_WEBHOOK_KEY` and `N8N_WEBHOOK_URL` (also supported as process
environment variables). The URL is pinned to the existing authenticated n8n webhook;
changing the destination requires a deliberate source change. No secret is sent to Gemini.
Recipient email is masked locally before model calls and sent to n8n only on confirmation.
Other user-provided title/date text does reach Gemini: do not include confidential details.

Only an in-memory action draft/clarification context is retained, isolated by browser cookie,
for up to 20 minutes of inactivity (128-session bound). Tabs in the same browser share that
session; a restart discards it. A new question after a complete proposal clears all of that
proposal’s fields, recipient and confirmation; provide the full replacement request. The action
payload is immutable at confirmation: the browser sends only its ID and confirm/cancel choice.
Double confirmation does not resend. Network uncertainty and partial email failure have no
automatic retries; inspect Calendar/n8n before creating another request. Restarting loses
this local duplicate guard, so it is not durable cross-session idempotency.

Success requires the workflow's explicit outcome and event/email IDs, not just HTTP 200.
Email accepted by the provider does not prove inbox delivery. The workflow must be active
and its Calendar/email credentials valid. Availability/conflict checks, production access,
durable idempotency, systematic model/date evaluation and assignment evaluation/report remain
out of scope. This is a partially operational action prototype, not a completed assignment.

## Cost and privacy boundaries

- Uses only `gemini-3.1-flash-lite`, provisionally listed with free Standard input/output on the [official pricing page](https://ai.google.dev/gemini-api/docs/pricing). It worked in the initial trial; future availability and shared quotas are not guaranteed. No alternative-model fallback or paid features are enabled.
- Do not enable API billing. An API key does not let this script verify or enforce Google billing status. Stop using it if that project later becomes paid.
- Quotas are shared with your n8n automations in the same project. API errors, including exhausted quota, stop the process without application-level retries.
- Free-service prompts and responses may be used by Google to improve products. Do not ask personal questions or send private student records, confidential material, or unreviewed screenshots. A private GitHub repo does not make API transmissions private. See [Google's terms](https://ai.google.dev/gemini-api/terms).
- The source teaching notebook contains an apparent credential and must not be imported unchanged. `.env`, notebook files and local model cache are ignored. No key is bundled here.

## What is covered

All actual `archivos_RAG/*.pdf` files are discovered at startup, skipping byte-identical duplicates. The prior full-corpus inspection covered **24 files / 23 unique PDFs / 149 pages**: 106 native-text pages and 43 pages with **unverified OCR**. No selected page remained empty or failed, but this is not a quality guarantee. Blank-extraction pages receive local macOS Vision OCR cached by original PDF SHA256 under ignored `.cache-prototype/ocr/`; source PDFs are never rewritten.

**Local-only documents:** `manual_descarga.pdf` and `manual_mp.pdf` contain screenshots with identity/account fields that have not been verified synthetic (36 pages). The two raw 2026 calendars (`RCS 2_26…` and `RR 435_26…`, 16 pages) also remain local-only because extraction contains hidden/stale text and unresolved variants. All four files can be searched with `--retrieve-only`. They and their byte-identical copies are excluded before the answer index is built, and the evidence tool rechecks eligibility before sending context to Gemini. Calendar answer evidence comes from `knowledge/calendar_2026.json`, with all variants grouped by event. The offline Chroma benchmark used **19 unique eligible PDFs / 97 pages**, plus **102 curated calendar records**. The file gate is not automatic personal-data detection or redaction; review any new file before adding it and update `LOCAL_ONLY_FILES` when needed. Tables, OCR and document applicability still require review.

Inspect all PDFs:

```sh
.venv/bin/python prototype_rag.py --inspect
```

Inspect or retrieve from explicitly selected PDFs locally:

```sh
.venv/bin/python prototype_rag.py --retrieve-only --files CorrelativasLicInformatica.pdf --question "¿Qué correlativas se mencionan?"
```

Custom file lists remain local-only in this prototype. Inspection labels cloud eligibility and reports extraction/OCR and curated-record coverage. `--files` omits curated records; `--calendar-only --inspect` validates just the curated calendar without PDF dependencies. An exact duplicate is skipped rather than indexed twice. Quick OCR requires macOS with Swift and Vision; no OCR dependencies are installed. It is not visually quality-validated. Calendar events are rendered into readable Spanish automatically from the validated JSON; the original PDFs are unchanged. General PDF-to-Markdown conversion is not implemented.

## How it works and what remains

`PDF extraction/OCR + validated calendar → token-aware chunks → local embeddings and ChromaDB → document search or calendar browse → bounded cited evidence → Gemini answer`

Chunks target 100 tokenizer tokens with 15-token overlap, below the embedding model's 128-token limit. Each semantic tool query is checked against the 128-token embedding limit and must be shortened rather than silently truncated. Gemini can reformulate a longer user question into a concise query. There is no calibrated relevance cutoff: an unrelated question still retrieves nearest neighbors. Similarity is not confidence or measured Precision/Recall; the prompt asks the model to decline unsupported answers, but this is not a factuality or prompt-injection guarantee. Citations are model-generated and must be checked. Calendar records preserve documented amendment scope and unresolved differences; no official-currentness guarantee or automatic institutional conflict resolution is implemented.

Calendar browsing returns every matching record, not four arbitrary hits. Source conflicts remain in one complete evidence unit; undated events remain undated. Calendar event titles do not automatically establish that classes are suspended. The model must interpret explicit evidence rather than assume this.

The four assignment deliverables remain: use-case/system-prompt/model design; Python/LangChain document RAG; LLM intent/date extraction and n8n Calendar/email actions; retrieval Precision/Recall experiments and a final architecture/results report. This prototype addresses document Q&A and a confirmed Calendar/email action slice in the local web chat. Career scope, authoritative corpus/versioning, availability rules and deployment remain open. The action uses the existing n8n instance; local webhook-key configuration is required.

## Record the experiment

The [offline retrieval benchmark](evaluation/README.md) compares the original in-memory baseline and the local Chroma index on the same ten labeled development questions. It measures ranked retrieval, not answer accuracy. For manual answer review, try a supported question, an ambiguous one and an unrelated one. Record the supporting passage and any extraction errors. See [project status](docs/PROJECT_STATUS.md) for the remaining OCR, factual and end-to-end checks.
