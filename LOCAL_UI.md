# Local chat

Double-click **Abrir asistente.command**, then use <http://127.0.0.1:8765>.
Leave its Terminal window running; close it or press Ctrl+C to stop the server.
Alternatively run `.venv/bin/python -B local_chat.py` from the repository.

Install the dependencies in `requirements-prototype.txt` before opening the chat.
Opening the page does not contact Gemini. The first question loads the local model
and opens or builds the persistent Chroma index. Only eligible evidence is used in
answers. Later restarts reuse the saved corpus vectors if nothing changed; the
first query still has to load the model. Close other instances before changing
documents, then restart the assistant to pick up the new corpus.
Questions are independent, with no conversational memory. The existing model,
quota, privacy guards and `.env` confirmations are unchanged. Free-tier flags are
not a billing lock. This loopback-only prototype is not a production web server.
