# Curated 2026 calendar: evidence and limits

The supplied calendar PDFs contain conflicting dates and hidden native-text rows. Answer mode uses **102 curated event records**, not raw calendar extraction. This is a transcription of supplied sources, not an official/current calendar certification.

## Verify offline

```sh
.venv/bin/python -B -m unittest discover -s tests -v
python3 -B prototype_rag.py --calendar-only --inspect
```

Calendar-only inspection uses Python's standard library; the full offline suite uses the installed virtual environment because retrieval tests import `langchain_core`. Neither command reads `.env`, extracts PDFs, downloads embeddings or calls Gemini. Full `--inspect` also extracts the other PDFs and may invoke local OCR; it does not use a model or key.

For semantic retrieval of only curated records, use the normal environment with cached/installed embedding dependencies:

```sh
.venv/bin/python prototype_rag.py --calendar-only --retrieve-only --question "¿Cuándo comienza la inscripción a finales de julio de 2026?"
```

That retrieval command may download the embedding model on first use. It was **not** executed as part of calendar unit verification.

## Source review

`knowledge/calendar_2026.json` stores original filenames, SHA256 digests, visually reviewed human PDF pages and coverage limits. The implementation's source review rendered and inspected all **14 RCS 2/26 pages and both RR 435/26 pages**. Native text was used only as a transcription aid and compared against rendered pages. Hidden rows were excluded even when extracted text supplied plausible dates.

| Source pages | Curated content |
| --- | --- |
| RCS p1 | Art. 1 enables December 28/29 exam boards in Annex 1 and fixes May 11-15 Extension/Innovation days; Art. 2 defines the general degree/modality scope. |
| RCS p2-4 | Visible Annex 1 event rows for January-December, including holidays and telework labels. Calendar grid numbers are not independent events. |
| RCS p5-14 | Visible Annex 2 rows, including `A DEFINIR` and the approximate April first-week event. Identical cross-annex events share evidence; substantive variants remain together. |
| RR p1-2 | November suspension dates and campus/modality scope, asynchronous alternatives, rescheduling requirements and ad-referendum status. |

The 102 records comprise 68 documented events, 26 date-to-be-defined events, 3 unresolved differences, 2 source anomalies, 2 amendment events and 1 approximate-date event. Month context for `A DEFINIR` is not an invented date range.

## Differences and anomalies that must remain visible

| Event | Supplied evidence | Required behavior |
| --- | --- | --- |
| July/August regular-finals registration | Annex 1 p3: July 6; Annex 2 p9: July 2. | Show both and seek university clarification. Annex 2 is not expressly a separate modality. |
| New entrants, second semester | Dedicated Annex 1 p3 row and Annex 2 p11: August 8; combined Annex 1 p3 conditional-course row also mentions new entrants on August 14. | Preserve the ambiguity; do not assume different enrollment categories. |
| December finals window | Annex 1 p4: December 7-29; Annex 2 p14: December 7-26. Art. 1 p1 explicitly enables December 28/29 in Annex 1. | Explain the express Annex 1 amendment without asserting a formal Annex 2 amendment. The broad window overlaps nonworking/holiday rows and is not a specific exam slot. |
| Research-call deadline | Annex 2 p14 visibly prints **29/12/2029** inside its December 2026 agenda. | Preserve the literal year and flag the anomaly, rather than silently correcting to 2026. |
| December 31 | Annex 1 p4 labels **31/12/2026** “Año nuevo”. | Preserve the printed label/date, not an inferred January 1 or legal holiday claim. |

RR 435/26 describes November 9 suspension in all campuses (Mar de Ajó, Mar del Plata, Dolores, CABA), both modalities. November 11 is restricted to campuses in Buenos Aires province, both modalities; do not automatically apply it to CABA. It requires rescheduling and allows asynchronous coverage, but supplies **no replacement dates**. Its ad-referendum approval and submission for future homologation do not prove subsequent homologation. These are claims about the supplied resolution, not independently verified national/provincial law.

## Data and retrieval contract

- Each record is an event-sized atomic evidence unit with a stable ID, scope, status, variants and source/page/section references. Conflict variants must never be split into independent retrieval records.
- `calendar_knowledge.py` validates structure, identities, ISO dates/ranges, explicit anomalies, source pages, visual-review markers, coverage and the 8000-character budget. It does **not** verify truth or resolve institutional applicability.
- Chunking supports local semantic search; after a hit, `expand_hits` restores the **whole record**, including every variant. No curated record may exceed the evidence budget. Answer mode uses general evidence tools: ranked semantic search or complete calendar browsing with optional year/date filters. Calendar browsing has no four-record cap; it returns every matching record that fits the cumulative 160,000-character evidence budget, with counts and explicit incomplete-coverage notices. The current 102 records fit that budget. Ranked search can still miss events; no measured retrieval guarantee is claimed.
- Both raw calendar PDFs remain **LOCAL-ONLY** alongside the two screenshot manuals. Raw calendar text can be inspected in local retrieval, where it remains unsafe as canonical dates. Answer-mode filtering occurs before top-k and the final formatter rejects local-only evidence.
- Default inspection includes curated coverage. `--files` is explicitly selected PDF-only local work and omits curated records. `--calendar-only` permits inspection/local retrieval only and cannot combine with `--files`.
- Missing, malformed or invalid curated data fails closed with an application-authored error. It never falls back to contradictory raw calendar text for cloud answers.

## Next checks

1. Have the team/university confirm the unresolved differences and applicable source versions.
2. Run labeled semantic-retrieval questions for dates, campus restrictions, unknown dates and unsupported questions. Measure evidence recall before tuning prompts/models.
3. If separately authorized, test Gemini answers and citations against the actual retrieved records; unit tests alone do not establish answer correctness.
