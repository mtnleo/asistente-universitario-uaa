"""Bounded evidence tools shared by CLI and web. No credentials or model loading."""
from datetime import date
import json
import re

MAX_CONTEXT_CHARS = 160_000
MAX_MODEL_CALLS = 3
MAX_TOOL_CALLS_PER_ROUND = 3

TOOLS = [
    {"type": "function", "function": {
        "name": "search_documents",
        "description": "Search university documents and calendar events by semantic relevance. Use a concise Spanish search query. This is ranked evidence, NOT an exhaustive list; use browse_calendar for complete calendar lists, periods, holidays or comparisons.",
        "parameters": {"type": "object", "properties": {
            "query": {"type": "string", "description": "Concise search query, at most 128 embedding tokens."}
        }, "required": ["query"], "additionalProperties": False}}},
    {"type": "function", "function": {
        "name": "browse_calendar",
        "description": "Read ALL curated calendar events, optionally constrained by calendar year and inclusive date interval, NOT by similarity/top-k. Prefer this for calendar questions, complete lists, comparisons and questions where event terminology is uncertain. With no filters it reads the entire available calendar. Classify events from explicit source statements, not assumptions: an academic event does not imply suspended classes. Read every page if complete=false. Undated events are retained unless include_undated=false. Sources preserve conflicts and campus/modality scope.",
        "parameters": {"type": "object", "properties": {
            "year": {"type": "integer", "description": "Calendar edition year; omit for all available years."},
            "start_date": {"type": "string", "description": "Optional YYYY-MM-DD inclusive interval start."},
            "end_date": {"type": "string", "description": "Optional YYYY-MM-DD inclusive interval end."},
            "include_undated": {"type": "boolean", "description": "Include events whose date is pending or approximate; default true."},
            "offset": {"type": "integer", "description": "Default 0; use next_offset to continue an incomplete result."}
        }, "additionalProperties": False}}},
]

TOOL_INSTRUCTIONS = """\nUse the evidence tools before answering; do not answer from your own knowledge.
You have up to two retrieval rounds and then must give a final answer. Choose and
rephrase searches yourself; there are no prewritten answers. For calendar dates,
lists, comparisons or uncertain event names, browse_calendar can read the complete
calendar, without similarity truncation. A ranked search is never proof that an
unretrieved event is absent. For an exhaustive request, browse all matching calendar
records; check total_matching and complete. If a result is incomplete, continue with
next_offset if possible; otherwise explicitly say the answer is partial. Date filters
can exclude relevant records, so broaden them if evidence is missing. Undefined dates
and conflicts must remain undefined/conflicting. Never equate an academic event or
commemoration with suspension of classes unless the evidence explicitly says so.
Cite only supplied S identifiers and actual PDF page references. No outside facts.
"""


def calendar_text(record):
    """Render existing facts into readable prose; do not add or classify facts."""
    statuses = {
        'documented': 'documentado', 'unresolved_difference': 'diferencia no resuelta (unresolved_difference)',
        'date_to_be_defined': 'fecha a definir', 'approximate_date': 'fecha aproximada',
        'source_anomaly': 'anomalía literal de la fuente', 'documented_amendment': 'modificación documentada',
    }
    lines = [f"Calendario {record['year']}. {record['event']}.", f"Estado: {statuses[record['status']]}." ]
    for variant in record['variants']:
        start, end = variant.get('start'), variant.get('end')
        when = start if start == end and start else f"{start} al {end}" if start and end else variant['date_text']
        lines.append(f"Fecha: {when}. Referencia: {variant['source_section']}.")
    scope = record['scope']
    for field, label in [('programs', 'Carreras'), ('modalities', 'Modalidades'), ('campuses', 'Sedes')]:
        value = scope[field]
        lines.append(f"{label}: {', '.join(value) if isinstance(value, list) else value}.")
    if scope.get('qualification'):
        lines.append(f"Alcance: {scope['qualification']}.")
    if record.get('notes'):
        lines.append(f"Aclaraciones: {record['notes']}")
    if record.get('responsible_area'):
        lines.append(f"Área responsable: {record['responsible_area']}.")
    return '\n'.join(lines)


class EvidenceSession:
    """Per-question stable citation registry with a cumulative serialized-size budget."""
    def __init__(self, rag, store, tokenizer, pages, budget=MAX_CONTEXT_CHARS):
        self.rag, self.store, self.tokenizer, self.pages = rag, store, tokenizer, pages
        self.budget, self.used = budget, 0
        self.sources, self.keys, self.notices = [], {}, []
        self.lookup = {(p['source'], p.get('record_id') or p['page']): p for p in pages}

    def add(self, page):
        if page.get('cloud_allowed') is not True:
            raise self.rag.PrototypeInputError('Local-only evidence cannot be sent to Gemini.')
        key = (page['source'], page.get('record_id') or page['page'])
        if key in self.keys:
            return {'id': self.keys[key], 'already_provided': True}
        text = page['text']
        # Calendar units are never partially truncated: all variants stay together.
        if not page.get('record_id') and len(text) > 8000:
            text = text[:8000] + '\n[PAGE TRUNCATED AT 8000 CHARACTERS]'
            notice = 'Una página PDF fue recortada a 8000 caracteres; no es evidencia completa de esa página.'
            if notice not in self.notices:
                self.notices.append(notice)
        source = {'id': f'S{len(self.sources) + 1}', 'source': page['source'], 'page': page['page'],
                  'record_id': page.get('record_id'), 'evidence': page.get('evidence', []),
                  'extraction': page['extraction'], 'text': text}
        size = len(json.dumps(source, ensure_ascii=False))
        if self.used + size > self.budget:
            notice = 'El presupuesto de contexto no permite incluir toda la evidencia; la respuesta puede ser parcial.'
            if notice not in self.notices:
                self.notices.append(notice)
            return None
        self.used += size
        self.sources.append(source)
        self.keys[key] = source['id']
        return source

    def search_documents(self, query):
        if not isinstance(query, str) or not query.strip() or len(query) > 2000:
            raise ValueError('query must be a nonempty short string')
        tokens = self.tokenizer.encode(query, add_special_tokens=True, truncation=False)
        if len(tokens) > self.rag.EMBEDDING_MAX_TOKENS:
            return {'error': 'Search query exceeds 128 embedding tokens. Rephrase it more briefly.', 'complete': False}
        hits = self.store.similarity_search_with_score(
            query, k=24, filter=lambda doc: doc.metadata.get('cloud_allowed') is True)
        sources, seen = [], set()
        omitted = False
        for hit, _ in hits:
            key = (hit.metadata['source'], hit.metadata.get('record_id') or hit.metadata['page'])
            if key in seen:
                continue
            seen.add(key)
            page = self.lookup[key]
            source = self.add(page)
            if source is None:
                omitted = True
                break
            sources.append(source)
        return {'mode': 'ranked_search', 'exhaustive': False,
                'candidate_units_seen': len(seen), 'returned': len(sources),
                'context_truncated': omitted, 'sources': sources,
                'warning': 'Ranked results are not an exhaustive list or evidence that other events do not exist.'}

    def browse_calendar(self, year=None, start_date=None, end_date=None, include_undated=True, offset=0):
        if year is not None and (type(year) is not int or not 1900 <= year <= 2200):
            raise ValueError('invalid year')
        if type(offset) is not int or offset < 0 or type(include_undated) is not bool:
            raise ValueError('invalid pagination or include_undated')
        for value in (start_date, end_date):
            if value is not None and (not isinstance(value, str) or date.fromisoformat(value).isoformat() != value):
                raise ValueError('invalid ISO date')
        if start_date and end_date and start_date > end_date:
            raise ValueError('reversed dates')
        matches = []
        for page in self.pages:
            record = page.get('calendar_record')
            if not record or page.get('cloud_allowed') is not True or (year is not None and record['year'] != year):
                continue
            variants = record['variants']
            dated = [v for v in variants if v.get('start') and v.get('end')]
            if not dated:
                if not include_undated:
                    continue
            elif (start_date or end_date) and not any(
                    (not start_date or v['end'] >= start_date) and (not end_date or v['start'] <= end_date)
                    for v in dated):
                continue
            matches.append(page)
        if offset > len(matches):
            raise ValueError('offset exceeds result count')
        sources, cursor = [], offset
        for page in matches[offset:]:
            source = self.add(page)
            if source is None:
                break
            sources.append(source)
            cursor += 1
        complete = offset == 0 and cursor == len(matches)
        page_complete = cursor == len(matches)
        return {'mode': 'calendar_browse', 'total_matching': len(matches), 'offset': offset,
                'returned': len(sources), 'complete': complete, 'page_complete': page_complete,
                'next_offset': None if page_complete else cursor,
                'context_budget_exhausted': not page_complete, 'sources': sources,
                'scope': 'All source variants and scope are preserved; an event does not itself imply no classes.'}

    def execute(self, name, args):
        allowed = {'search_documents': {'query'},
                   'browse_calendar': {'year', 'start_date', 'end_date', 'include_undated', 'offset'}}
        if name not in allowed or not isinstance(args, dict) or not set(args) <= allowed[name]:
            return {'error': 'Unknown tool or unsupported arguments. Use only the declared evidence tools.'}
        try:
            return getattr(self, name)(**args)
        except (ValueError, TypeError, KeyError):
            return {'error': 'Invalid tool arguments. Correct the declared arguments and try again.'}


def answer_question(rag, chat, store, tokenizer, pages, question):
    """Native tool selection, at most two retrieval rounds and one final generation."""
    from langchain_core.messages import SystemMessage, HumanMessage, ToolMessage

    session = EvidenceSession(rag, store, tokenizer, pages)
    messages = [SystemMessage(content=rag.SYSTEM_PROMPT + TOOL_INSTRUCTIONS), HumanMessage(content=question)]
    # Require the first grounding call; preserve returned AIMessage thought signatures.
    tool_chat = chat.bind_tools(TOOLS, tool_choice='any')
    for round_number in range(2):
        response = tool_chat.invoke(messages)
        messages.append(response)
        calls = response.tool_calls or []
        if not calls:
            break
        for index, call in enumerate(calls):
            result = (session.execute(call.get('name'), call.get('args')) if index < MAX_TOOL_CALLS_PER_ROUND
                      else {'error': 'Tool-call limit reached. Use the evidence already retrieved.'})
            messages.append(ToolMessage(content=json.dumps(result, ensure_ascii=False), tool_call_id=call['id']))
        if round_number == 0:
            # The second round may refine retrieval or finish immediately.
            tool_chat = chat.bind_tools(TOOLS)
    if not session.sources:
        return {'answer': 'No se obtuvo evidencia suficiente. No puedo responder con respaldo documental.',
                'sources': [], 'notices': session.notices}
    # If the second round returned an answer without calls, it is already grounded.
    if not calls:
        answer = response.text or 'El modelo no devolvió una respuesta de texto.'
    else:
        messages.append(HumanMessage(content='Ahora respondé usando solo la evidencia obtenida. No hay más herramientas disponibles. Si la cobertura es parcial, indicá esa limitación.'))
        response = chat.invoke(messages)
        answer = response.text or 'El modelo no devolvió una respuesta de texto.'
    referenced = set(re.findall(r'\bS\d+\b', answer))
    if referenced - {source['id'] for source in session.sources}:
        answer = 'La respuesta generada incluyó citas que no corresponden a la evidencia recuperada. No la presento como verificada; revisá las fuentes o reformulá la pregunta.'
    if response.response_metadata.get('finish_reason') in {'MAX_TOKENS', 'max_tokens'}:
        session.notices.append('La respuesta alcanzó el límite de salida y puede estar incompleta.')
    if session.notices:
        answer += '\n\n**Limitaciones:** ' + ' '.join(session.notices)
    return {'answer': answer, 'sources': session.sources, 'notices': session.notices}
