"""Offline action tests: fake model and HTTP, no keys or real service calls."""
from pathlib import Path
import sys
import unittest
from unittest.mock import patch, Mock
from datetime import datetime, timedelta
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from calendar_actions import ActionSessions, ZONE, send_event
import prototype_rag as rag
from rag_tools import answer_question
from langchain_core.messages import AIMessage


def fields():
    start = datetime.now(ZONE).replace(microsecond=0) + timedelta(days=2)
    return dict(title='Consulta', start=start.isoformat(), end=(start+timedelta(minutes=17)).isoformat())


class ActionTest(unittest.TestCase):
    def setup_draft(self, sender=None):
        actions = ActionSessions(sender=sender or Mock(return_value='created'))
        token, session = actions.get(None)
        actions.context(session, 'Consulta a estudiante@example.org')
        pending = actions.propose(session, fields())['pending']
        return actions, token, session, pending

    def test_confirmation_is_single_use_and_isolated(self):
        sender = Mock(return_value='created')
        actions, token, session, pending = self.setup_draft(sender)
        sender.assert_not_called()
        other, _ = actions.get(None)
        with self.assertRaises(ValueError): actions.decide(other, pending['id'], True)
        actions.decide(token, pending['id'], True)
        actions.decide(token, pending['id'], True)
        sender.assert_called_once()
        self.assertTrue(sender.call_args.args[0]['confirmed'])

    def test_cancel_expiry_and_uncertainty_never_retry(self):
        actions, token, session, pending = self.setup_draft()
        actions.decide(token, pending['id'], False)
        actions.sender.assert_not_called()
        actions, token, session, pending = self.setup_draft(Mock(side_effect=TimeoutError))
        self.assertIn('incierto', actions.decide(token, pending['id'], True)['answer'])
        actions.decide(token, pending['id'], True)
        actions.sender.assert_called_once()
        actions.clock = lambda: session['seen'] + 1201
        with self.assertRaises(ValueError): actions.decide(token, pending['id'], True)

    def test_new_request_cannot_inherit_complete_proposal(self):
        actions, token, session, pending = self.setup_draft()
        session['history'] = ['Previous complete request']
        context = actions.context(session, 'Creá un evento llamado Segundo')
        result = actions.propose(session, {'title': 'Segundo'})
        self.assertEqual(context, 'Creá un evento llamado Segundo')
        self.assertNotIn('pending', result)
        self.assertIsNone(session['pending'])
        self.assertEqual(session['draft'], {'title': 'Segundo'})
        self.assertEqual(session['email'], '')
        for missing in ('fecha y hora de inicio', 'hora de fin', 'correo destinatario'):
            self.assertIn(missing, result['answer'])
        with self.assertRaises(ValueError): actions.decide(token, pending['id'], True)
        actions.sender.assert_not_called()

    def test_validation_and_missing_fields(self):
        actions = ActionSessions(); _, session = actions.get(None)
        self.assertIn('falta', actions.propose(session, {})['answer'])
        self.assertTrue(session['active'])
        for args in ({'confirmed': True}, {'title': 123}, {'start': '2026-11-07T10:00:00'}):
            with self.assertRaises(ValueError): actions.propose(session, args)
        draft=fields();draft['end']=draft['start']
        actions.context(session, 'estudiante@example.org')
        with self.assertRaises(ValueError): actions.propose(session, draft)

    def test_model_proposes_without_network_and_email_is_masked(self):
        actions=ActionSessions(sender=Mock());_, session=actions.get(None)
        context=actions.context(session,'Creá consulta para estudiante@example.org')
        self.assertNotIn('estudiante@example.org', context)
        class Chat:
            def bind_tools(self, tools, **kwargs): return self
            def invoke(self, messages):
                self.messages=messages
                return AIMessage(content='', tool_calls=[{'name':'propose_calendar_action','id':'a','args':fields()}])
        chat=Chat()
        result=answer_question(rag,chat,None,None,[],context,action_handler=lambda args:actions.propose(session,args),action_context='Server clock: '+datetime.now(ZONE).isoformat())
        self.assertIn('pending',result);actions.sender.assert_not_called()
        self.assertIn('Server clock:',chat.messages[0].content)

    @patch('calendar_actions.webhook_config', return_value=('https://n8n.mtnleo-n8n.org/webhook/ia2-calendar-action', 'test-only'))
    @patch('calendar_actions.request.build_opener')
    def test_http_outcomes(self, opener, config):
        import json
        response=opener.return_value.open.return_value.__enter__.return_value
        cases=[(200,{},'unknown'),(200,{'status':'event_created_email_accepted','eventId':'e','emailMessageId':'m'},'created'),(200,{'status':'event_created_email_accepted','eventId':'e'},'unknown')]
        for code, body, expected in cases:
            response.status=code;response.read.return_value=json.dumps(body).encode()
            self.assertEqual(send_event({}),expected)
            sent = opener.return_value.open.call_args.args[0]
            self.assertEqual(sent.get_header('User-agent'), 'IA2UniversityAssistant/1.0')
        from urllib.error import HTTPError
        from io import BytesIO
        opener.return_value.open.side_effect=HTTPError('https://example.org',502,'',{},BytesIO(b'{"status":"event_created_email_unconfirmed","eventId":"e"}'))
        self.assertEqual(send_event({}),'email_unconfirmed')
        opener.return_value.open.side_effect=TimeoutError
        self.assertEqual(send_event({}),'unknown')
        config.return_value=('https://example.org','test-only')
        self.assertEqual(send_event({}),'not_configured')


if __name__ == '__main__': unittest.main()
