"""Validate curated calendar data without PDF, model, or credential dependencies."""
from datetime import date
import json
import re


class CalendarDataError(ValueError):
    """Only application-authored descriptions; never echo untrusted file contents."""


def _require(condition, message):
    if not condition:
        raise CalendarDataError(message)


def _text(value):
    return isinstance(value, str) and bool(value.strip())


def validate_calendar(data):
    """Fail closed: every evidence unit needs dates/status, scope and visual provenance.

    This checks internal consistency, not source truth, official currentness, or law.
    A conflict is atomic: all variants live in the same record for hit expansion.
    """
    _require(isinstance(data, dict), 'Calendar must be an object.')
    _require(type(data.get('schema_version')) is int and data['schema_version'] == 1,
             'Unsupported calendar schema version.')
    _require(type(data.get('year')) is int and data['year'] == 2026, 'Expected calendar year 2026.')
    coverage = data.get('coverage')
    _require(isinstance(coverage, dict), 'Missing calendar coverage.')
    for key in ('method', 'included', 'excluded'):
        _require(_text(coverage.get(key)), 'Missing coverage description.')
    _require(isinstance(coverage.get('limitations'), list) and coverage['limitations']
             and all(_text(v) for v in coverage['limitations']), 'Missing coverage limitations.')
    sources = coverage.get('reviewed_sources')
    _require(isinstance(sources, list) and sources, 'Missing reviewed sources.')
    reviewed = {}
    for source in sources:
        _require(isinstance(source, dict), 'Invalid reviewed source.')
        filename = source.get('file')
        _require(_text(filename) and '/' not in filename and '\\' not in filename
                 and filename.endswith('.pdf') and filename not in reviewed, 'Invalid source filename.')
        _require(isinstance(source.get('sha256'), str)
                 and re.fullmatch(r'[0-9a-f]{64}', source['sha256']), 'Invalid source digest.')
        n = source.get('pages')
        _require(type(n) is int and n > 0, 'Invalid source page count.')
        pages = source.get('visually_reviewed_pages')
        _require(isinstance(pages, list) and pages and all(type(p) is int and 1 <= p <= n for p in pages)
                 and len(set(pages)) == len(pages), 'Invalid visually reviewed pages.')
        reviewed[filename] = set(pages)
    records = data.get('records')
    _require(isinstance(records, list) and records, 'Missing calendar records.')
    _require(type(coverage.get('record_count')) is int and coverage['record_count'] == len(records),
             'Calendar coverage count mismatch.')
    ids = set()
    statuses = {'documented', 'unresolved_difference', 'date_to_be_defined',
                'approximate_date', 'source_anomaly', 'documented_amendment'}
    for record in records:
        _require(isinstance(record, dict), 'Invalid calendar record.')
        identity = record.get('id')
        _require(_text(identity) and identity == identity.strip() and identity not in ids,
                 'Missing or duplicate record identity.')
        ids.add(identity)
        _require(type(record.get('year')) is int and record['year'] == data['year'], 'Wrong record year.')
        _require(_text(record.get('event')), 'Missing calendar event.')
        status = record.get('status')
        _require(isinstance(status, str) and status in statuses, 'Invalid record status.')
        _require(isinstance(record.get('notes'), str), 'Missing record notes.')
        scope = record.get('scope')
        _require(isinstance(scope, dict), 'Missing event scope.')
        for key in ('programs', 'modalities'):
            _require(isinstance(scope.get(key), list) and scope[key] and all(_text(v) for v in scope[key]),
                     'Missing program/modality scope.')
        campuses = scope.get('campuses')
        _require(_text(campuses) or (isinstance(campuses, list) and campuses and all(_text(v) for v in campuses)),
                 'Missing campus scope.')
        _require(_text(scope.get('qualification')), 'Missing scope qualification.')
        evidence = record.get('evidence')
        _require(isinstance(evidence, list) and evidence, 'Missing source evidence.')
        for item in evidence:
            _require(isinstance(item, dict), 'Invalid source evidence.')
            _require(_text(item.get('file')) and item['file'] in reviewed, 'Unknown evidence source.')
            _require(type(item.get('page')) is int and item['page'] in reviewed[item['file']],
                     'Evidence page was not visually reviewed.')
            _require(_text(item.get('section')), 'Missing source section.')
            _require(item.get('verification') == 'rendered_page_visual_review', 'Unverified evidence method.')
        variants = record.get('variants')
        _require(isinstance(variants, list) and variants, 'Missing event variants.')
        ranges = set()
        for variant in variants:
            _require(isinstance(variant, dict), 'Invalid event variant.')
            _require(_text(variant.get('date_text')) and _text(variant.get('source_section')),
                     'Missing literal date or variant source.')
            _require('start' in variant and 'end' in variant, 'Missing variant date fields.')
            start, end = variant['start'], variant['end']
            if status in {'date_to_be_defined', 'approximate_date'}:
                _require(start is None and end is None, 'An undefined date must not be fabricated.')
                _require(type(variant.get('month_context')) is int and 1 <= variant['month_context'] <= 12,
                         'Undefined date needs month context.')
            else:
                try:
                    _require(isinstance(start, str) and isinstance(end, str)
                             and re.fullmatch(r'\d{4}-\d{2}-\d{2}', start)
                             and re.fullmatch(r'\d{4}-\d{2}-\d{2}', end), 'Invalid date format.')
                    first, last = date.fromisoformat(start), date.fromisoformat(end)
                except (ValueError, TypeError):
                    raise CalendarDataError('Invalid calendar date.') from None
                _require(first <= last, 'Reversed date range.')
                _require(status == 'source_anomaly' or first.year == last.year == data['year'],
                         'Out-of-year dates require explicit source anomaly.')
            ranges.add((start, end))
        if status == 'unresolved_difference':
            _require(len(ranges) >= 2 and _text(record['notes']), 'Unresolved difference requires grouped variants and notes.')
        if status in {'source_anomaly', 'documented_amendment', 'approximate_date'}:
            _require(_text(record['notes']), 'Exceptional status requires an explanation.')
        _require(len(json.dumps(record, ensure_ascii=False, indent=2)) <= 8000,
                 'Calendar evidence unit exceeds 8000 characters; simplify without splitting conflict variants.')
    return data
