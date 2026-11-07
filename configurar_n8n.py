#!/usr/bin/env python3
"""Explicit local setup. Never prints, transmits or loads an existing secret."""
from getpass import getpass
from pathlib import Path
import json
import os
from calendar_actions import URL


def main():
    path = Path(__file__).with_name('.env.n8n')
    if path.exists():
        raise SystemExit('Ya existe .env.n8n. Editalo localmente para cambiar la configuración.')
    key = getpass('Clave X-IA2-Key de n8n (entrada oculta): ')
    if not key or any(c in key for c in '\r\n'):
        raise SystemExit('Clave vacía o inválida. No se guardó nada.')
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w') as out:
        out.write('N8N_WEBHOOK_URL=' + URL + '\nN8N_WEBHOOK_KEY=' + json.dumps(key) + '\n')
    print('Configuración guardada localmente. Reiniciá el chat. No se envió ninguna acción.')


if __name__ == '__main__':
    main()
