# Asistente universitario UAA

Trabajo grupal de Inteligencia Artificial II. El asistente responde preguntas sobre reglamentos, trámites y calendario académico a partir de los documentos del proyecto. En el chat se pueden revisar las fuentes de cada respuesta.

[Informe final (PDF)](docs/IA2-Informe-Final.pdf) · [Evaluación de la búsqueda](evaluation/README.md)

## Instalación

Para probar el asistente con todos los documentos, use macOS con Python 3.12 y las herramientas de línea de comandos de Xcode. Algunas páginas escaneadas requieren OCR local con Swift y Vision. Desde la carpeta del repositorio:

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements-prototype.txt
```

## Prueba sin clave de API

```sh
.venv/bin/python prototype_rag.py --inspect
.venv/bin/python -m unittest discover -s tests -v
```

El primer comando muestra qué documentos y registros de calendario se pudieron leer. Los dos comandos se ejecutan sin Gemini ni n8n.

## Si usa Windows

El chat completo requiere macOS para leer los PDF escaneados. En Windows, la página puede abrirse, pero la primera consulta puede fallar al procesar esos archivos.

Con Python 3.12, puede inspeccionar los 102 registros del calendario desde la carpeta del repositorio, sin instalar dependencias ni configurar una clave:

```powershell
py -3.12 -X utf8 prototype_rag.py --calendar-only --inspect
```

Este comando no abre el chat ni llama a Gemini. Para ver ejemplos de respuestas y sus fuentes, consulte las capturas del [informe final](docs/IA2-Informe-Final.pdf).

## Probar el chat

1. Si todavía no existe, copie `.env.example` a `.env`. En ese archivo, configure `GOOGLE_API_KEY` con una clave propia de un proyecto de Gemini sin facturación habilitada. Marque `FREE_TIER_CONFIRMED=true` y `ALLOW_DOCUMENT_SNIPPETS=true` únicamente si verificó que el proyecto usa el nivel gratuito y está autorizado a enviar fragmentos de los documentos a Gemini. No suba `.env` al repositorio.
2. Desde la carpeta del repositorio, ejecute:

   ```sh
   .venv/bin/python -B local_chat.py
   ```

3. Abra [el chat local](http://127.0.0.1:8765) y pruebe: «¿Qué establece el reglamento sobre la regularidad?». Debajo de la respuesta podrá consultar las fuentes. Para cerrar el servidor, presione Ctrl+C en la terminal.

Abrir el chat no llama a Gemini. En la primera consulta puede descargarse el modelo de búsqueda local (MiniLM) y se prepara el índice de ChromaDB. No incluya información personal o confidencial en las preguntas.

La creación de eventos y el envío de correos son opcionales: requieren un flujo de n8n configurado y una confirmación en el chat. No hacen falta para probar las consultas sobre documentos.
