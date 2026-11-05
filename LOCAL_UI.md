# Local chat

Double-click **Abrir asistente.command**, then use <http://127.0.0.1:8765>.
Leave its Terminal window running; close it or press Ctrl+C to stop the server.
Alternatively run `.venv/bin/python -B local_chat.py` from the repository.

No new dependencies. Opening the page does not contact Gemini. Sending a question
initializes the existing local PDF/calendar index once and sends the question and
cloud-eligible retrieved evidence to Gemini. The first query can take longer while
the local embedding model loads (and can download model files if not cached).
The index stays in memory until the server stops; restart after changing documents.
Questions are independent, with no conversational memory. The existing model,
quota, privacy guards and `.env` confirmations are unchanged. Free-tier flags are
not a billing lock. This loopback-only prototype is not a production web server.
