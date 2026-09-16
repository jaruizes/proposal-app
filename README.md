# Proposal App — UX Prototype

Angular prototype for validating the proposal-generation workflow UI.

## What is mocked

- Offer creation and auto-generated UUID.
- Workflow phases and state transitions.
- Automatic transition from **Trabajando** to **Esperando aprobación**.
- Human approval triggering the next phase.
- Refinement chat returning a phase to **Trabajando**.
- Markdown-like artifact preview.
- AI provider/model selectors.
- Presentation guidance section editor.

No backend, Google Drive or LLM calls are performed yet.

## Run

```bash
npm install
npm start
```

Then open `http://localhost:4200`.
