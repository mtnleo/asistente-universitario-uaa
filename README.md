# UAA University Assistant

University-assistant project for the IA 2 integrative assignment. This repository is an initial scaffold, not a working application.

## Required deliverables

1. Define the university use case, choose an LLM, and design its system prompt, tone, limits, and response format.
2. Build document retrieval and grounded answers with Python, LangChain, embeddings, and a vector database using authoritative source documents.
3. Extract action intent and dates with the LLM, call n8n through webhooks, and implement appointment booking in Google Calendar with confirmation email.
4. Measure retrieval Precision and Recall, compare configuration changes, and document the architecture, development, and results.

The assignment timeline is tentative; the deliverables remain the target.

## Open decisions

- Which careers, study plans, and university services are in scope.
- Which calendars, regulations, and other official documents form the source corpus, and how to collect and refresh them.
- Which appointment service, calendar owner, availability rules, and user details the action requires.
- Model provider, embeddings, vector database, interface, and deployment.

An existing Raspberry Pi 5 runs n8n continuously and is available if needed. It is not a hosting requirement for the application.

## Public-repository safety

Keep credentials, personal data, local document collections, generated indexes, and notebook outputs out of Git. Review source permissions before publishing university documents. The supplied teaching notebook contains an apparent embedded credential and must not be imported unchanged.

## Next step

Agree on the first career/service scope and identify authoritative documents before implementing collection or application code.
