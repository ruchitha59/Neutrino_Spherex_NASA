# SPHEREx Explorer API

This service queries IRSA SIA2, retrieves real SPHEREx MEF cutouts from the returned `access_url`, validates their FITS structure, and runs the Member 2 science pipeline. No demo frames are returned.

## Run locally (Windows PowerShell)

From the project root:

```powershell
py -3.12 -m pip install -r backend/requirements.txt
py -3.12 -m uvicorn app:app --app-dir backend --reload --host 127.0.0.1 --port 8000
```

In another terminal:

```powershell
cd spherex-frontend
npm install
npm run dev
```

The Vite development server proxies `/api` to port 8000. Open the URL it prints (normally `http://localhost:5173`). API docs are at `http://127.0.0.1:8000/docs`. Set `SPHEREX_API_TARGET` before `npm run dev` to use a different API port.

## API

- `GET /api/health`
- `POST /api/search` with `ra`, `dec`, `fov`, and `data_release`
- `POST /api/jobs` with the returned `search_id` (automatically selects up to six observations from the most populated single band)
- `GET /api/jobs/{job_id}`
- `GET /api/results/{job_id}`
- `GET /api/media/{job_id}/{filename}` for generated preview PNGs

Data products are stored under `data/api/jobs/`. Search and job state is held in process memory, so restart clears active job records. Use one QR collection and one spectral band per comparison. The frontend defaults to a 0.5-degree field because real tests show it supplies enough stable background sources for alignment; smaller fields remain available. If IRSA's cutout endpoint is busy, the API retries and then downloads the same real full FITS product as a fallback; the pipeline reprojects it onto the cutout-sized reference grid. An empty archive result remains empty; motion/variability signals are preliminary and unverified. Ambiguous residuals remain in the processing output but are kept out of the review queue.

## Supported science environment

Python 3.12, NumPy 1.x, Astropy, SciPy, reproject, Photutils, and Matplotlib. The Member 2 package is included under `SPHEREx_Member2/`.
