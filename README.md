# Proposal App

Monorepo prototype for the proposal-generation application.

## Structure

```text
frontend/   Angular UI prototype
backend/    reserved for the backend implementation
```

## Run the frontend

```bash
cd frontend
npm install
npm start
```

Then open `http://localhost:4200`.

The current frontend uses mocks for offer creation, workflow execution, approvals and refinement. No backend, Google Drive or LLM calls are performed yet.
