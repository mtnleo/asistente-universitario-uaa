"""Offline calendar tests: no keys, model downloads, PDF extraction, or APIs."""
import contextlib
import copy
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

import prototype_rag as app
from calendar_knowledge import CalendarDataError, validate_calendar

ROOT = Path(__file__).resolve().parents[1]


class Document:
    def __init__(self, page_content, metadata):
        self.page_content, self.metadata = page_content, metadata


class CalendarTests(unittest.TestCase):
    def setUp(self):
        self.data = json.loads((ROOT / 'knowledge/calendar_2026.json').read_text())

    def invalid(self, change):
        change(self.data)
        with self.assertRaises(CalendarDataError):
            validate_calendar(self.data)

    def test_dataset_validates_and_counts(self):
        validate_calendar(self.data)
        self.assertEqual(len(self.data['records']), 102)
        self.assertEqual(self.data['coverage']['record_count'], 102)

    def test_duplicate_identity_rejected(self):
        self.invalid(lambda d: d['records'][1].update(id=d['records'][0]['id']))

    def test_blank_identity_rejected(self):
        self.invalid(lambda d: d['records'][0].update(id=' '))

    def test_invalid_calendar_date_rejected(self):
        self.invalid(lambda d: d['records'][0]['variants'][0].update(start='2026-02-30'))

    def test_reversed_range_rejected(self):
        self.invalid(lambda d: d['records'][0]['variants'][0].update(start='2026-02-01'))

    def test_wrong_year_requires_explicit_anomaly(self):
        self.invalid(lambda d: d['records'][0]['variants'][0].update(start='2029-01-01', end='2029-01-01'))

    def test_missing_provenance_rejected(self):
        self.invalid(lambda d: d['records'][0].update(evidence=[]))

    def test_unknown_source_rejected(self):
        self.invalid(lambda d: d['records'][0]['evidence'][0].update(file='other.pdf'))

    def test_malformed_evidence_filename_rejected(self):
        self.invalid(lambda d: d['records'][0]['evidence'][0].update(file=[]))

    def test_unreviewed_page_rejected(self):
        self.invalid(lambda d: d['records'][0]['evidence'][0].update(page=15))

    def test_boolean_page_rejected(self):
        self.invalid(lambda d: d['records'][0]['evidence'][0].update(page=True))

    def test_invisible_method_rejected(self):
        self.invalid(lambda d: d['records'][0]['evidence'][0].update(verification='native_text'))

    def test_missing_coverage_rejected(self):
        self.invalid(lambda d: d.pop('coverage'))

    def test_bad_status_rejected(self):
        self.invalid(lambda d: d['records'][0].update(status='resolved_by_guess'))

    def test_conflict_cannot_be_single_variant(self):
        self.invalid(lambda d: d['records'][0].update(status='unresolved_difference'))

    def test_conflicts_grouped_and_source_dates_preserved(self):
        by_id = {r['id']:r for r in self.data['records']}
        self.assertEqual({v['start'] for v in by_id['regular-july-registration']['variants']}, {'2026-07-02','2026-07-06'})
        self.assertEqual({v['end'] for v in by_id['finals-dec']['variants']}, {'2026-12-26','2026-12-29'})
        self.assertEqual({v['start'] for v in by_id['new-second-deadline']['variants']}, {'2026-08-08','2026-08-14'})
        self.assertEqual(by_id['research-call-close-anomaly']['variants'][0]['start'], '2029-12-29')
        self.assertIn('does not expressly amend Annex2', by_id['finals-dec']['notes'])

    def test_undefined_dates_never_fabricated(self):
        for r in self.data['records']:
            if r['status'] in {'date_to_be_defined','approximate_date'}:
                self.assertTrue(all(v['start'] is None and v['end'] is None for v in r['variants']))

    def test_rr435_scope_and_no_replacement_date(self):
        by_id = {r['id']:r for r in self.data['records']}
        self.assertEqual(by_id['suspension-nov9']['scope']['campuses'], ['Mar de Ajó','Mar del Plata','Dolores','CABA'])
        self.assertEqual(by_id['suspension-nov11']['scope']['campuses'], ['sedes ubicadas en provincia de Buenos Aires'])
        for id in ['suspension-nov9','suspension-nov11']:
            self.assertIn('No replacement dates given', by_id[id]['notes'])
            self.assertIn('ad referendum', by_id[id]['notes'])
            self.assertEqual(len(by_id[id]['evidence']), 2)

    def test_hidden_rows_excluded(self):
        text=json.dumps(self.data, ensure_ascii=False).lower()
        for phrase in ['carga de nombramiento', 'programa analítico completo', 'carga de mesas de exámenes', 'inducción a la docencia']:
            self.assertNotIn(phrase, text)

    def test_loader_missing_file_has_safe_error(self):
        with patch.object(app, 'CALENDAR_KNOWLEDGE', Path('/does-not-exist-calendar.json')):
            with self.assertRaisesRegex(app.PrototypeInputError, 'missing'):
                app.load_calendar_records()

    def test_loader_malformed_json_has_safe_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'bad.json';path.write_text('{secret not JSON')
            with patch.object(app, 'CALENDAR_KNOWLEDGE', path):
                with self.assertRaisesRegex(app.PrototypeInputError, 'invalid JSON') as error:
                    app.load_calendar_records()
            self.assertNotIn('secret', str(error.exception))

    def test_loader_schema_error_has_safe_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'bad.json';path.write_text('{}')
            with patch.object(app, 'CALENDAR_KNOWLEDGE', path):
                with self.assertRaisesRegex(app.PrototypeInputError, 'schema'):
                    app.load_calendar_records()

    def test_loader_preserves_complete_units_under_budget(self):
        pages, report=app.load_calendar_records()
        self.assertEqual(report['records'], 102)
        for p in pages:
            self.assertLessEqual(len(p['text']), 8000)
            self.assertEqual(p['page'], None)
            self.assertTrue(p['cloud_allowed'])
            self.assertEqual(p['calendar_record']['id'], p['record_id'])

    def test_expand_hit_restores_both_july_variants(self):
        pages,_=app.load_calendar_records()
        p=next(p for p in pages if p['record_id']=='regular-july-registration')
        hit=Document('truncated chunk', {k:v for k,v in p.items() if k!='text'})
        module=types.ModuleType('langchain_core.documents');module.Document=Document
        with patch.dict(sys.modules, {'langchain_core.documents':module}):
            result=app.expand_hits([(hit,0.8),(hit,0.7)],pages)
        self.assertEqual(len(result),1)
        text=result[0][0].page_content
        self.assertIn('2026-07-02',text);self.assertIn('2026-07-06',text)
        self.assertIn('unresolved_difference',text)
        payload=json.loads(app.format_context(result))
        self.assertEqual(payload[0]['record_id'],'regular-july-registration')
        self.assertEqual({e['page'] for e in payload[0]['evidence']},{1,3,9})

    def test_raw_calendars_remain_blocked_even_without_files_on_disk(self):
        self.assertTrue(any(name.startswith('RCS 2_26') for name in app.CALENDAR_RAW_FILES))
        for name in app.CALENDAR_RAW_FILES:
            self.assertIn(name, app.LOCAL_ONLY_FILES)
            hit=Document('raw hidden text', {'source':name,'page':1,'cloud_allowed':False})
            with self.assertRaises(app.PrototypeInputError):
                app.format_context([(hit,0.9)])

    def test_default_inspection_loads_calendar_without_keys_or_models(self):
        with patch.object(sys,'argv',['prototype_rag.py','--inspect']), \
             patch.object(app,'load_pages',return_value=([],[])), \
             patch.object(app,'answer_config',side_effect=AssertionError('No keys')), \
             patch.object(app,'build_store',side_effect=AssertionError('No models')), \
             contextlib.redirect_stdout(io.StringIO()) as output:
            app.main()
        self.assertIn('curated_calendar_records',output.getvalue())
        self.assertIn('102',output.getvalue())

    def test_calendar_only_inspection_is_dependency_free(self):
        proc=subprocess.run([sys.executable,'-B','prototype_rag.py','--calendar-only','--inspect'],cwd=ROOT,capture_output=True,text=True)
        self.assertEqual(proc.returncode,0,proc.stderr)
        self.assertIn('102',proc.stdout)

    def test_calendar_only_requires_inspection_or_local_retrieval(self):
        with patch.object(sys,'argv',['prototype_rag.py','--calendar-only']):
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                app.main()


if __name__ == '__main__':
    unittest.main()
