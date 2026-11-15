# SPHEREx Explorer frontend

The React/Vite interface searches live SPHEREx products through the FastAPI service. It displays real archive provenance, processed image previews, quality masks, comparison products, timeline controls, and preliminary candidate reports. It does not provide demo observations when the archive has no coverage.

## Run locally (Windows PowerShell)

From the project root, start the API:

```powershell
py -3.12 -m pip install -r backend/requirements.txt
py -3.12 -m uvicorn app:app --app-dir backend --reload --host 127.0.0.1 --port 8000
```

In a second terminal:

```powershell
cd spherex-frontend
npm install
npm run dev
```

Vite runs at `http://localhost:5173` and proxies `/api` to the local FastAPI server. Set `$env:SPHEREX_API_TARGET` before `npm run dev` to use a different API URL.

## Verify

```powershell
npm run lint
npm test
npm run build
```

The Member 2 suite runs from `SPHEREx_Member2` with `py -3.12 -m pytest -q`. See the root `INTEGRATION_STATUS.md` for the live-data verification and known scientific/data-availability limitations.
