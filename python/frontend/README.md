# HILIGHTer Browser Frontend

This directory contains the React/Vite browser client for HILIGHTer.

Current status:

- It is a secondary interface, not the primary supported operator workflow.
- It consumes a subset of the FastAPI backend exposed by `python/backend/main.py`.
- Several requests still use older compatibility routes such as `/simulate` and `/results/fisher/{n_photons}`.
- If the HTTP API changes, this frontend must be updated in lockstep.

## Requirements

- Node.js and `npm`
- a Python environment with `python/requirements.txt` installed
- the FastAPI backend running from the repository root

## Install and Run

From the repository root:

```powershell
python -m pip install -r python\requirements.txt
python -m uvicorn python.backend.main:app --reload
```

In a second terminal:

```powershell
cd python/frontend
npm install
npm run dev
```

Expected backend:

```powershell
python -m uvicorn python.backend.main:app --reload
```

## Notes

- The frontend currently targets `http://localhost:8000` directly from `src/App.jsx`.
- It is intentionally thinner than the desktop app and does not expose every workspace capability.
- The maintained API surface is moving toward `/api/v1/...`, but the frontend still depends on a few compatibility routes.
