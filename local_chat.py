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
/* Quiet daytime reading surface, with one restrained action color. */
:root{color-scheme:light;--page:oklch(97.5% .006 165);--surface:oklch(99.5% .003 165);--ink:oklch(25% .014 165);--muted:oklch(45% .016 165);--line:oklch(86% .014 165);--accent:oklch(39% .075 165);--soft:oklch(94% .018 165)}
*{box-sizing:border-box}
body{max-width:800px;margin:0 auto;padding:40px 28px 32px;background:var(--page);color:var(--ink);font:16px/1.65 -apple-system,BlinkMacSystemFont,system-ui,sans-serif}
header{display:flex;align-items:baseline;justify-content:space-between;gap:16px;padding-bottom:20px;border-bottom:1px solid var(--line)}
header h1{margin:0;font-size:1.25rem;line-height:1.3;letter-spacing:-.025em;font-weight:650}
.badge{font-size:.875rem;color:var(--muted);white-space:nowrap}
.intro{margin:36px 0 24px}.intro h2{margin:0 0 8px;font-size:1.75rem;line-height:1.25;letter-spacing:-.035em;font-weight:600}
.note{color:var(--muted);margin:0;max-width:65ch}
label{display:block;margin-bottom:8px;font-size:.875rem;font-weight:600}
.composer{padding:16px;background:var(--surface);border:1px solid var(--line);border-radius:16px;box-shadow:0 3px 12px oklch(25% .014 165 / .035)}
.composer:focus-within{border-color:var(--accent)}
textarea{display:block;width:100%;font:inherit;resize:vertical;min-height:100px;border:0;border-radius:4px;background:transparent;color:var(--ink);padding:0 2px}
textarea::placeholder{color:var(--muted);opacity:1}
.composer-footer{display:flex;align-items:center;justify-content:space-between;gap:16px;margin-top:16px}
.hint{font-size:.875rem;color:var(--muted)}
button{font:inherit;cursor:pointer;min-height:44px;flex-shrink:0;font-size:.9375rem;font-weight:600;padding:10px 20px;background:var(--accent);color:var(--surface);border:1px solid transparent;border-radius:9px;transition:background-color 160ms ease-out,transform 160ms ease-out}
button:hover{background:oklch(32% .075 165)}button:active:not(:disabled){transform:translateY(1px)}
button:disabled{opacity:.55;cursor:wait}button.secondary{background:transparent;color:var(--ink);border-color:var(--line)}button.secondary:hover{background:var(--soft)}
:focus-visible{outline:3px solid var(--accent);outline-offset:4px}
#status{min-height:1.65em;margin:16px 0;font-size:.875rem;color:var(--muted)}
#status[data-state="error"]{color:oklch(43% .14 28)}#status[data-state="success"]{color:var(--accent)}#status[data-state="loading"]{color:var(--accent);font-weight:600}
#response{margin:28px 0 36px}.section-label{margin:0 0 16px;font-size:.875rem;font-weight:650;color:var(--muted)}
#answer{max-width:70ch;overflow-wrap:anywhere}#answer p{margin:.8em 0}#answer h1,#answer h2,#answer h3{margin:1.4em 0 .5em;line-height:1.3}#answer h1{font-size:1.5rem}#answer h2{font-size:1.25rem}#answer h3{font-size:1.125rem}#answer code{font-family:ui-monospace,monospace;font-size:.9em;padding:.15em .3em;border-radius:4px}#answer pre{overflow-x:auto}#answer pre code{padding:0}#answer blockquote{margin:1em 0}pre{white-space:pre-wrap;overflow-wrap:anywhere;font:14px/1.6 system-ui}#answer>:first-child{margin-top:0}#answer li{margin:.35em 0}
#answer code,#answer pre,#answer blockquote{background:var(--soft)}#answer pre,#answer blockquote{padding:12px 16px;border-radius:8px}
#sources:not(:empty){margin-top:28px;padding-top:20px;border-top:1px solid var(--line)}#sources h3{margin:0 0 8px;font-size:.875rem;color:var(--muted)}
details{margin:0;border:0;border-bottom:1px solid var(--line);padding:0}
summary{padding:12px 4px;min-height:44px;font-size:.875rem;overflow-wrap:anywhere}summary:hover{color:var(--accent)}
details pre{margin:0;padding:4px 4px 16px;color:var(--muted)}
#action:not(:empty){margin:24px 0;padding:20px;background:var(--soft);border:1px solid var(--line);border-radius:12px}
#action h2{font-size:1.125rem;line-height:1.3;margin:0 0 8px}#action p{font-size:.875rem;color:var(--muted);margin:0 0 16px}
#action dl{margin:0 0 20px;display:grid;grid-template-columns:70px minmax(0,1fr);gap:8px 16px;font-size:.9375rem}
#action dt{color:var(--muted)}#action dd{margin:0;overflow-wrap:anywhere}.action-buttons{display:flex;flex-wrap:wrap;gap:12px}
footer{margin-top:36px;padding-top:20px;border-top:1px solid var(--line);font-size:.875rem;color:var(--muted)}footer p{margin:0 0 12px}footer details{border:0}footer summary{padding-left:0}
@media(max-width:540px){body{padding:24px 20px}header{align-items:flex-start;gap:8px;flex-direction:column}.intro{margin-top:28px}.intro h2{font-size:1.5rem}.composer-footer{align-items:flex-start;flex-direction:column;gap:12px}.composer-footer button{align-self:flex-end}}
@media(prefers-reduced-motion:reduce){button{transition:none;transform:none!important}}
</style>
<header><h1>Asistente universitario</h1><span class="badge">UAA · Prototipo local</span></header>
<main>
<div class="intro"><h2>¿Qué necesitás consultar?</h2><p class="note">Consultá fechas, trámites y documentos de la universidad, con fuentes para revisar.</p></div>
<form id="form"><label for="question">Tu pregunta</label><div class="composer"><textarea id="question" rows="3" maxlength="2000" required aria-describedby="question-hint" placeholder="¿Cuándo son los exámenes finales de diciembre de 2026?"></textarea><div class="composer-footer"><span class="hint" id="question-hint">Una consulta a la vez, hasta 2000 caracteres.</span><button id="send">Preguntar</button></div></div></form>
<p id="status" role="status" aria-live="polite" aria-atomic="true"></p>
<div id="action" aria-live="polite"></div>
<section id="response" aria-label="Respuesta" hidden><h2 class="section-label">Respuesta</h2><div id="answer"></div><div id="sources"></div></section>
</main>
<footer><p>Prototipo, no información oficial. Verificá las fuentes antes de tomar una decisión.</p><details><summary>Cómo funciona y qué datos se envían</summary><p>Busca en los documentos locales y responde con Gemini. La primera pregunta prepara el índice y puede tardar. Solo se envían a Gemini la pregunta y los fragmentos permitidos. Las preguntas documentales son independientes.</p><p>Los datos de un evento se conservan solo para aclararlo y confirmarlo (20 minutos). El correo destinatario queda local hasta confirmar su envío a n8n.</p></details></footer>
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
  const heading=document.createElement('h2');heading.textContent='Revisá el evento antes de enviar';
  const note=document.createElement('p');note.textContent='Solo se enviará a n8n si confirmás. Esto no implica una reserva institucional.';
  const summary=document.createElement('dl');
  const dateLabel=value=>{const date=new Date(value);return Number.isNaN(date.getTime())?String(value):new Intl.DateTimeFormat('es-AR',{dateStyle:'medium',timeStyle:'short',timeZone:'America/Argentina/Buenos_Aires'}).format(date)+' (Argentina)'};
  for(const [label,value] of [['Evento',pending.title],['Inicio',dateLabel(pending.start)],['Fin',dateLabel(pending.end)],['Correo',pending.email]]){
    const term=document.createElement('dt'),detail=document.createElement('dd');term.textContent=label;detail.textContent=value;summary.append(term,detail);
  }
  const actions=document.createElement('div');actions.className='action-buttons';box.append(heading,note,summary,actions);
  for(const [label,confirm] of [['Confirmar y enviar',true],['Cancelar',false]]){
    const b=document.createElement('button');b.type='button';b.textContent=label;if(!confirm)b.className='secondary';actions.append(b);
    b.onclick=async()=>{for(const x of box.querySelectorAll('button'))x.disabled=true;button.disabled=true;status.dataset.state='loading';status.textContent=confirm?'Enviando evento…':'Cancelando evento…';
      try{const r=await fetch('/action',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id:pending.id,confirm})});const data=await r.json();renderMarkdown(data.answer||data.error);box.replaceChildren();status.dataset.state=data.error?'error':'neutral';status.textContent=data.error?'No se pudo completar la acción.':'Revisá el resultado de la solicitud.';}
      catch{status.dataset.state='error';status.textContent='Resultado incierto. No repitas la solicitud; revisá Calendar/n8n.';}
      finally{button.disabled=false;}};
  }
}
function renderMarkdown(text){
  document.getElementById('response').hidden=false;
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
form.addEventListener('submit',async e=>{e.preventDefault();const question=q.value.trim();if(!question)return;button.disabled=true;button.textContent='Consultando…';form.setAttribute('aria-busy','true');status.dataset.state='loading';status.textContent='Buscando y preparando la respuesta… La primera consulta puede tardar más.';answer.textContent='';document.getElementById('response').hidden=true;sources.replaceChildren();showAction(null);try{const r=await fetch('/ask',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({question})});const data=await r.json();if(!r.ok)throw new Error(data.error||'No se pudo responder.');renderMarkdown(data.answer);showAction(data.pending);if(data.sources.length){const title=document.createElement('h3');title.textContent='Fuentes consultadas · '+data.sources.length;sources.append(title)}for(const source of data.sources){const d=document.createElement('details'),s=document.createElement('summary'),p=document.createElement('pre');s.textContent='['+source.id+'] '+source.source+(source.page?' · página '+source.page:'')+(source.record_id?' · '+source.record_id:'');p.textContent=source.text+(source.evidence.length?'\n\nProcedencia: '+JSON.stringify(source.evidence,null,2):'');d.append(s,p);sources.append(d)}status.dataset.state='success';status.textContent=data.pending?'Revisá el evento y confirmá si querés enviarlo.':'Respuesta lista. Podés revisar las fuentes o hacer otra consulta.'}catch(error){status.dataset.state='error';status.textContent=error.message||'No se pudo conectar con el servidor local.'}finally{button.disabled=false;button.textContent='Preguntar';form.removeAttribute('aria-busy')}});
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
