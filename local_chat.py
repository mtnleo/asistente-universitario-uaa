#!/usr/bin/env python3
"""Minimal loopback-only web UI for the existing RAG prototype."""
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Lock
from calendar_actions import ActionSessions, ZONE
from datetime import datetime
from http.cookies import SimpleCookie

HOST, PORT = '127.0.0.1', 8765
ORIGIN = f'http://{HOST}:{PORT}'
HTML = r'''<!doctype html>
<html lang="es"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Asistente universitario</title>
<style>
:root{color-scheme:light}body{font:16px/1.6 -apple-system,BlinkMacSystemFont,system-ui,sans-serif;background:oklch(98% .005 250);color:oklch(24% .01 250);max-width:740px;margin:48px auto;padding:0 20px}h1{font-size:1.7rem;line-height:1.2}textarea{box-sizing:border-box;width:100%;font:inherit;padding:12px;border:1px solid oklch(75% .01 250);border-radius:6px;resize:vertical}button{font:inherit;padding:9px 20px;background:oklch(42% .14 255);color:oklch(99% .005 250);border:0;border-radius:6px;cursor:pointer}button:hover{background:oklch(35% .14 255)}button:disabled{opacity:.6;cursor:wait}:focus-visible{outline:3px solid oklch(65% .15 255);outline-offset:3px}small,.note{color:oklch(43% .01 250)}#answer{overflow-wrap:anywhere}#answer p{margin:.7em 0}#answer h1,#answer h2,#answer h3{margin:1em 0 .4em;line-height:1.3}#answer h1{font-size:1.5rem}#answer h2{font-size:1.3rem}#answer h3{font-size:1.1rem}#answer ul,#answer ol{padding-left:1.5em}#answer code{font-family:ui-monospace,monospace;background:oklch(94% .005 250);padding:.1em .25em;border-radius:3px}#answer pre{background:oklch(94% .005 250);padding:12px;overflow-x:auto}#answer pre code{padding:0}#answer blockquote{margin:1em 0;padding:8px 12px;background:oklch(95% .005 250)}pre{white-space:pre-wrap;overflow-wrap:anywhere;font:14px/1.5 system-ui}details{margin:16px 0;border-top:1px solid oklch(85% .01 250);padding-top:10px}summary{cursor:pointer}#status{min-height:1.6em}
</style>
<h1>Asistente universitario</h1>
<p class="note">Busca en los documentos locales y responde con Gemini. Prototipo, no información oficial.</p>
<form id="form"><label for="question">Tu pregunta</label><textarea id="question" rows="3" maxlength="2000" required placeholder="¿Cuándo son los exámenes finales de diciembre de 2026?"></textarea><button id="send">Preguntar</button></form>
<p id="status" role="status" aria-live="polite"></p>
<div id="action" aria-live="polite"></div>
<section aria-label="Respuesta"><div id="answer"></div><div id="sources"></div></section>
<small>La primera pregunta prepara el índice y puede tardar. Solo se envían a Gemini la pregunta y los fragmentos permitidos. Las preguntas documentales son independientes. Los datos de un evento se conservan solo para aclararlo y confirmarlo (20 minutos). El correo destinatario queda local hasta confirmar su envío a n8n.</small>
<script>
const form=document.getElementById('form'),q=document.getElementById('question'),button=document.getElementById('send'),status=document.getElementById('status'),answer=document.getElementById('answer'),sources=document.getElementById('sources');
// Small local Markdown renderer: all model text becomes text nodes, never HTML.
function inlineMarkdown(parent,text){
  const pattern=/(`[^`\n]+`|\*\*[^*\n]+\*\*|__[^_\n]+__|\*[^*\n]+\*|_[^_\n]+_)/g;
  let start=0;
  for(const match of text.matchAll(pattern)){
    parent.append(document.createTextNode(text.slice(start,match.index)));
    const token=match[0],strong=token.startsWith('**')||token.startsWith('__');
    const el=document.createElement(token[0]==='`'?'code':strong?'strong':'em');
    el.textContent=token.slice(strong?2:1,strong?-2:-1);parent.append(el);start=match.index+token.length;
  }
  parent.append(document.createTextNode(text.slice(start)));
}
function showAction(pending){
  const box=document.getElementById('action');box.replaceChildren();if(!pending)return;
  const summary=document.createElement('pre');summary.textContent='Evento: '+pending.title+'\nInicio: '+pending.start+'\nFin: '+pending.end+'\nCorreo: '+pending.email;box.append(summary);
  for(const [label,confirm] of [['Confirmar y enviar',true],['Cancelar',false]]){
    const b=document.createElement('button');b.type='button';b.textContent=label;b.style.marginRight='12px';box.append(b);
    b.onclick=async()=>{for(const x of box.querySelectorAll('button'))x.disabled=true;button.disabled=true;
      try{const r=await fetch('/action',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id:pending.id,confirm})});const data=await r.json();renderMarkdown(data.answer||data.error);box.replaceChildren();status.textContent='';}
      catch{status.textContent='Resultado incierto. No repitas la solicitud; revisá Calendar/n8n.';}
      finally{button.disabled=false;}};
  }
}
function renderMarkdown(text){
  answer.replaceChildren();const lines=String(text).replace(/\r\n?/g,'\n').split('\n');
  let paragraph=null,list=null,listType=null;
  function reset(){paragraph=null;list=null;listType=null}
  for(let i=0;i<lines.length;i++){
    const line=lines[i];
    if(/^\s*```/.test(line)){
      reset();const pre=document.createElement('pre'),code=document.createElement('code'),content=[];
      while(++i<lines.length&&!/^\s*```/.test(lines[i]))content.push(lines[i]);
      code.textContent=content.join('\n');pre.append(code);answer.append(pre);continue;
    }
    if(!line.trim()){reset();continue}
    const heading=line.match(/^\s{0,3}(#{1,6})\s+(.+?)\s*#*$/);
    if(heading){reset();const el=document.createElement('h'+heading[1].length);inlineMarkdown(el,heading[2]);answer.append(el);continue}
    if(/^\s*(?:---+|\*\*\*+|___+)\s*$/.test(line)){reset();answer.append(document.createElement('hr'));continue}
    const item=line.match(/^\s*(?:([-+*])\s+|(\d+)[.)]\s+)(.*)$/);
    if(item){
      paragraph=null;const type=item[2]?'ol':'ul';
      if(!list||listType!==type){list=document.createElement(type);listType=type;if(type==='ol')list.start=Number(item[2]);answer.append(list)}
      const li=document.createElement('li');inlineMarkdown(li,item[3]);list.append(li);continue;
    }
    list=null;listType=null;
    const quote=line.match(/^\s*>\s?(.*)$/);
    if(quote){paragraph=null;const el=document.createElement('blockquote');inlineMarkdown(el,quote[1]);answer.append(el);continue}
    if(!paragraph){paragraph=document.createElement('p');answer.append(paragraph)}else paragraph.append(document.createElement('br'));
    inlineMarkdown(paragraph,line);
  }
}
form.addEventListener('submit',async e=>{e.preventDefault();const question=q.value.trim();if(!question)return;button.disabled=true;status.textContent='Buscando y preparando la respuesta… La primera consulta puede tardar más.';answer.textContent='';sources.replaceChildren();showAction(null);try{const r=await fetch('/ask',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({question})});const data=await r.json();if(!r.ok)throw new Error(data.error||'No se pudo responder.');renderMarkdown(data.answer);showAction(data.pending);for(const source of data.sources){const d=document.createElement('details'),s=document.createElement('summary'),p=document.createElement('pre');s.textContent='['+source.id+'] '+source.source+(source.page?' · página '+source.page:'')+(source.record_id?' · '+source.record_id:'');p.textContent=source.text+(source.evidence.length?'\n\nProcedencia: '+JSON.stringify(source.evidence,null,2):'');d.append(s,p);sources.append(d)}status.textContent='Listo.'}catch(error){status.textContent=error.message||'No se pudo conectar con el servidor local.'}finally{button.disabled=false}});
</script></html>'''


class Assistant:
    def __init__(self):
        self.lock = Lock()
        self.ready = False
        self.actions = ActionSessions()

    def ask(self, question, session):
        # Serialize questions and keep the expensive index alive between requests.
        with self.lock:
            import prototype_rag as rag
            if not self.ready:
                os.environ['GOOGLE_GENAI_USE_VERTEXAI'] = 'false'
                os.environ['LANGCHAIN_TRACING_V2'] = 'false'
                os.environ['LANGSMITH_TRACING'] = 'false'
                curated, _ = rag.load_calendar_records()
                key = rag.answer_config()
                names = sorted(p.name for p in rag.CORPUS.glob('*.pdf'))
                pages, _ = rag.load_pages(names)
                pages.extend(curated)
                store, tokenizer = rag.build_store(pages)
                chat = rag.make_chat(key)
                self.pages, self.store, self.tokenizer, self.chat = pages, store, tokenizer, chat
                self.ready = True
            from rag_tools import answer_question
            # context() invalidates complete proposals before extracting new fields.
            context = self.actions.context(session, question)
            result = answer_question(rag, self.chat, self.store, self.tokenizer, self.pages, context,
                action_handler=lambda args: self.actions.propose(session, args),
                action_context='Server clock: ' + datetime.now(ZONE).isoformat(timespec='seconds') +
                '. Timezone: America/Argentina/Buenos_Aires. Current draft: ' + json.dumps(session['draft']))
            if session['active']:
                session['history'] = [context[-6000:]]
            else:
                session['history'], session['email'] = [], ''
            return result



assistant = Assistant()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass  # Do not log user questions or provider details.

    def reply(self, code, data, content_type='application/json; charset=utf-8'):
        body = data.encode('utf-8') if isinstance(data, str) else json.dumps(data, ensure_ascii=False).encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        if getattr(self, 'session_token', None):
            self.send_header('Set-Cookie', 'ia2_session=' + self.session_token + '; HttpOnly; SameSite=Strict; Path=/')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('X-Frame-Options', 'DENY')
        self.end_headers()
        self.wfile.write(body)

    def local_request(self):
        return self.headers.get('Host') == f'{HOST}:{PORT}' and self.headers.get('Origin', ORIGIN) == ORIGIN

    def do_GET(self):
        if not self.local_request():
            return self.reply(403, {'error': 'Solo acceso local.'})
        if self.path == '/':
            return self.reply(200, HTML, 'text/html; charset=utf-8')
        if self.path == '/health':
            return self.reply(200, {'app': 'ia2-local-chat', 'ready': assistant.ready})
        self.reply(404, {'error': 'No encontrado.'})

    def do_POST(self):
        if not self.local_request() or self.headers.get('Origin') != ORIGIN:
            return self.reply(403, {'error': 'Solo se aceptan consultas desde la página local.'})
        if self.path not in {'/ask', '/action'}:
            return self.reply(404, {'error': 'No encontrado.'})
        if self.headers.get('Content-Type', '').split(';')[0] != 'application/json':
            return self.reply(415, {'error': 'Se requiere JSON.'})
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length <= 12000:
                raise ValueError()
            data = json.loads(self.rfile.read(length))
            if not isinstance(data, dict):
                raise ValueError()
            cookie = SimpleCookie(self.headers.get('Cookie', ''))
            token = cookie['ia2_session'].value if 'ia2_session' in cookie else None
            self.session_token, session = assistant.actions.get(token)
            if self.path == '/action':
                if set(data) != {'id', 'confirm'} or not isinstance(data['id'], str) or type(data['confirm']) is not bool:
                    raise ValueError()
                return self.reply(200, assistant.actions.decide(self.session_token, data['id'], data['confirm']))
            question = data.get('question')
            if not isinstance(question, str) or not question.strip() or len(question) > 2000:
                raise ValueError()
        except (ValueError, UnicodeDecodeError):
            return self.reply(400, {'error': 'Ingresá una pregunta de hasta 2000 caracteres.'})
        try:
            self.reply(200, assistant.ask(question.strip(), session))
        except ValueError as error:
            return self.reply(400, {'error': str(error)})
        except Exception as error:
            import prototype_rag as rag
            if isinstance(error, rag.PrototypeInputError):
                return self.reply(400, {'error': str(error)})
            self.reply(503, {'error': 'No se pudo completar la consulta. Revisá la configuración local, conexión o cuota de Gemini. No se reintentó ni se usó un modelo alternativo.'})


def main():
    try:
        server = ThreadingHTTPServer((HOST, PORT), Handler)
    except OSError:
        raise SystemExit(f'No se pudo abrir {ORIGIN}. El puerto puede estar ocupado. No se cerró ningún otro proceso.')
    print(f'Asistente disponible en {ORIGIN}. Ctrl+C para cerrar.', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
