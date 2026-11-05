#!/bin/bash
cd -- "$(dirname -- "$0")" || exit 1
if [ ! -x .venv/bin/python ]; then
  echo 'Falta .venv/bin/python. Revisá la instalación del prototipo.'
  read -r -p 'Presioná Enter para cerrar.'
  exit 1
fi
# Reuse only this application's server; never stop an unknown process.
if /usr/bin/curl --noproxy '*' --silent --max-time 2 http://127.0.0.1:8765/health | /usr/bin/grep -q '"app": "ia2-local-chat"'; then
  /usr/bin/open http://127.0.0.1:8765
  exit 0
fi
(sleep 1; /usr/bin/open http://127.0.0.1:8765) &
exec .venv/bin/python -B local_chat.py
