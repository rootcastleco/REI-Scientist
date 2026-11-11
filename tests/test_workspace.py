"""Tests for the local study workspace; no real device, network or LLM calls."""
import copy
import http.client
import json
from pathlib import Path
import tempfile
import threading
import unittest

from rei_scientist.workspace_store import (ConflictError, PROJECTS, WorkspaceError,
                                          WorkspaceStore, new_study, normalized_objective,
                                          plan_markdown, results_csv, validate_study)
from rei_scientist.workspace_app import WorkspaceHTTPServer, figure_svg
from rei_scientist.workspace_figure import export_figure


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = Path(self.tmp.name) / 'research.sqlite3'
        self.store = WorkspaceStore(self.db)

    def test_templates_all_valid_and_no_fake_measurements(self):
        for project in PROJECTS:
            s = new_study(project)
            self.assertEqual(validate_study(s), s)
            self.assertEqual(s['verification_status'], 'NOT VERIFIED')
            self.assertEqual(s['results'], [])
            self.assertTrue(s['research_question'])
            self.assertIn('J(x)', normalized_objective(s))

    def test_unsupported_unit_is_rejected(self):
        s = new_study('REI Track')
        s['variables'][0]['unit'] = 'parsecs_per_qubit'
        with self.assertRaisesRegex(WorkspaceError, 'Unsupported unit'):
            validate_study(s)

    def test_normalized_objective_detects_dimension_mismatch(self):
        s = new_study('GPS/IoT')
        s['objective']['terms'][0]['scale_unit'] = 'kg'
        with self.assertRaisesRegex(WorkspaceError, 'DIMENSION MISMATCH'):
            validate_study(s)

    def test_normalized_objective_accepts_compatible_units(self):
        s = new_study('REI Balance')
        s['variables'][0]['unit'] = 'm/s'
        self.assertEqual(validate_study(s), s)

    def test_rejects_nonfinite_and_invalid_bounds(self):
        s = new_study()
        s['tolerance'] = float('nan')
        with self.assertRaises(WorkspaceError):
            validate_study(s)
        s = new_study()
        s['variables'][0]['lower'] = 100
        s['variables'][0]['upper'] = 10
        with self.assertRaisesRegex(WorkspaceError, 'lower bound'):
            validate_study(s)

    def test_rejects_result_pass_without_values(self):
        s = new_study('REI Track')
        s['results'] = [{'variable': 'event_loss', 'baseline': None, 'candidate': 1.2, 'verification': 'PASS'}]
        with self.assertRaisesRegex(WorkspaceError, 'PASS cannot'):
            validate_study(s)

    def test_rejects_study_pass_without_provenance(self):
        s = new_study()
        s['verification_status'] = 'PASS'
        with self.assertRaisesRegex(WorkspaceError, 'Study PASS'):
            validate_study(s)

    def test_revision_search_filter_restore_and_conflicts(self):
        a = self.store.create(new_study('REI Track'))
        b = self.store.create(new_study('REI Balance'))
        self.assertEqual(a['revision'], 1)
        self.assertEqual(len(self.store.list()), 2)
        self.assertEqual(len(self.store.list(project='REI Track')), 1)
        self.assertEqual(self.store.list(q='GNSS')[0]['id'], a['id'])
        edit = copy.deepcopy(a['study'])
        edit['title'] = 'Canary latency'
        updated = self.store.update(a['id'], a['revision'], edit)
        self.assertEqual(updated['revision'], 2)
        with self.assertRaises(ConflictError):
            self.store.update(a['id'], 1, edit)
        self.assertEqual(len(self.store.history(a['id'])), 2)
        restored = self.store.restore(a['id'], 2, 1)
        self.assertEqual(restored['revision'], 3)
        self.assertEqual(restored['study']['title'], a['study']['title'])
        self.assertEqual(len(self.store.history(a['id'])), 3)
        self.assertEqual(b['revision'], 1)

    def test_search_escapes_like_wildcards(self):
        self.store.create(new_study('REI Track'))
        self.assertEqual(self.store.list(q='ZZZ%'), [])
        self.assertEqual(self.store.list(q='REI_'), [])

    def test_result_residual_and_empty_evidence(self):
        s = new_study()
        s['results'] = [{'variable': 'event_loss', 'baseline': 3.0, 'candidate': 2.5,
                         'verification': 'NOT VERIFIED'}]
        validated = validate_study(s)
        plan = plan_markdown(validated, 4)
        self.assertIn('Record revision: 4', plan)
        self.assertIn('-0.5', plan)
        self.assertIn('NOT VERIFIED', plan)
        self.assertIn('event_loss,%,3.0,2.5,-0.5,NOT VERIFIED', results_csv(s))
        self.assertIn('Residual', figure_svg(s))
        self.assertIn('2.5 %', figure_svg(s))

    def test_figure_svg_escapes_untrusted_content(self):
        s = new_study()
        s['title'] = '<img src=x onerror=alert(1)>'
        svg = figure_svg(s)
        self.assertNotIn('<img', svg)
        self.assertIn('&lt;img', svg)

    def test_optional_matplotlib_outputs_actual_files(self):
        try:
            import matplotlib  # noqa
        except ImportError:
            self.skipTest('matplotlib optional dependency not installed')
        s = new_study('GPS/IoT')
        s['results'] = [{'variable': 'latency', 'baseline': 300, 'candidate': 240,
                         'verification': 'NOT VERIFIED'}]
        rec = self.store.create(s)
        png, svg = export_figure(self.db, rec['id'], Path(self.tmp.name)/'plots'/'latency')
        self.assertEqual(png.read_bytes()[:8], b'\x89PNG\r\n\x1a\n')
        self.assertIn('<svg', svg.read_text())
        with self.assertRaises(FileExistsError):
            export_figure(self.db, rec['id'], png.with_suffix(''))


class HttpTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.server = WorkspaceHTTPServer(('127.0.0.1', 0), WorkspaceStore(Path(self.tmp.name)/'db.sqlite'))
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)

    def request(self, method, path, body=None, token=None, origin=None, host=None):
        con = http.client.HTTPConnection('127.0.0.1', self.server.server_port, timeout=4)
        headers = {'Host':host or f'127.0.0.1:{self.server.server_port}'}
        if body is not None:
            headers['Content-Type']='application/json'
        if token is not None:
            headers['X-REI-Token']=token
        if origin is not None:
            headers['Origin']=origin
        con.request(method, path, body=json.dumps(body).encode('utf-8') if body is not None else None, headers=headers)
        response=con.getresponse()
        data=response.read()
        code=response.status
        con.close()
        return code, data

    def test_serves_secure_local_ui(self):
        code, body=self.request('GET','/')
        self.assertEqual(code,200)
        self.assertIn(b'REI Scientist',body)
        code, body=self.request('GET','/app.js')
        self.assertEqual(code,200)
        self.assertIn(b'NOT VERIFIED', body)

    def test_host_and_token_origin_guards(self):
        _, content=self.request('GET','/api/bootstrap')
        token=json.loads(content)['token']
        s=new_study()
        code,_=self.request('POST','/api/studies',{'study':s})
        self.assertEqual(code,403)
        code,_=self.request('POST','/api/studies',{'study':s},token=token,host='malicious.test')
        self.assertEqual(code,403)
        code,_=self.request('POST','/api/studies',{'study':s},token=token,origin='http://malicious.test')
        self.assertEqual(code,403)
        code,body=self.request('POST','/api/studies',{'study':s},token=token)
        self.assertEqual(code,201)
        identifier=json.loads(body)['id']
        code,body=self.request('GET','/api/studies/'+identifier+'/plan.md')
        self.assertEqual(code,200)
        self.assertIn(b'NOT VERIFIED',body)
        code,body=self.request('GET','/api/studies/'+identifier+'/results.csv')
        self.assertEqual(code,200)
        self.assertIn(b'residual',body)

    def test_rejects_schema_invalid_and_no_extra_methods(self):
        _, content=self.request('GET','/api/bootstrap')
        token=json.loads(content)['token']
        code,_=self.request('POST','/api/studies',{'study':{'invalid':True}},token=token)
        self.assertEqual(code,422)
        code,_=self.request('PUT','/api/studies',{'study':new_study()},token=token)
        self.assertEqual(code,405)


if __name__=='__main__':
    unittest.main()
