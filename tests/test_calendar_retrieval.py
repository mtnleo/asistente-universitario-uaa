"""Focused general-tool regression, offline: no keys, embeddings or API calls."""
import json
from pathlib import Path
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import prototype_rag as rag
from rag_tools import EvidenceSession, answer_question
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.documents import Document


class Tokenizer:
    def encode(self, text, **kwargs): return text.split()


class Store:
    def __init__(self, pages): self.pages=pages
    def similarity_search_with_score(self, query, k, filter):
        return [(Document(page_content=p['text'],metadata={key:value for key,value in p.items() if key!='text'}),.8)
                for p in self.pages[:1] if filter(Document(page_content=p['text'],metadata=p))]


class Chat:
    def __init__(self): self.calls=0;self.messages=[]
    def bind_tools(self, tools, **kwargs): return self
    def invoke(self, messages):
        self.messages.append(list(messages));self.calls+=1
        if self.calls==1:
            return AIMessage(content='',tool_calls=[{'id':'first','name':'search_documents','args':{'query':'feriados calendario 2026'}}],additional_kwargs={'signature_test':'preserve'})
        if self.calls==2:
            return AIMessage(content='',tool_calls=[{'id':'second','name':'browse_calendar','args':{'year':2026}}])
        return AIMessage(content='Calendario consultado completo [S1].')


class GeneralRetrievalTest(unittest.TestCase):
    def test_tool_grounding_complete_calendar_and_boundaries(self):
        pages,_=rag.load_calendar_records();store=Store(pages);chat=Chat()
        result=answer_question(rag,chat,store,Tokenizer(),pages,'Listá los feriados de todo el año 2026.')
        self.assertEqual((chat.calls,len(result['sources'])),(3,102))
        payload=json.loads(next(m.content for m in chat.messages[-1] if isinstance(m,ToolMessage) and m.tool_call_id=='second'))
        self.assertTrue(payload['complete']);self.assertEqual(payload['total_matching'],102)
        december=next(s for s in result['sources'] if s['record_id']=='finals-dec')
        self.assertTrue(all(d in december['text'] for d in ['2026-12-26','2026-12-29']))
        self.assertEqual(len({s['id'] for s in result['sources']}),102)
        self.assertEqual(chat.messages[-1][2].additional_kwargs['signature_test'],'preserve')
        session=EvidenceSession(rag,store,Tokenizer(),pages,budget=100)
        self.assertFalse(session.browse_calendar(year=2026)['complete'])
        with self.assertRaises(rag.PrototypeInputError): session.add({'cloud_allowed':False})
        self.assertIn('error',session.execute('__class__',{}))
        print(f'Full calendar: {len(result["sources"])} records; serialized source chars: {sum(len(json.dumps(s,ensure_ascii=False)) for s in result["sources"])}; 3 model calls (fake).')


if __name__=='__main__': unittest.main()
