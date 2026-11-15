# Member 3 Integration Guide

## Stable entry point

```python
from science.pipeline import process_manifest

result = process_manifest(
    manifest_path="data/manifest.json",
    output_dir="data/results/job_123",
    config_path="config/default.json",
)
```

The function returns a JSON-serializable dictionary containing `status`, `frames`, `comparisons`, `warnings`, `errors` and `candidate_count`.

It also writes:

- `job_123/results/processing.json`
- `job_123/results/candidates.json`
- `job_123/processed/*.fits`
- `job_123/previews/*.png`

## CLI

```powershell
python -m science.pipeline --manifest data/manifest.json --output-dir data/results/job_123 --config config/default.json
```

## Recommended backend flow

1. Member 3 validates the request and resolves selected observation IDs to Member 1 manifest records.
2. Member 3 creates a job-specific manifest containing only selected records, retaining the original record fields.
3. Member 3 calls `process_manifest(...)` in a worker or background task.
4. Member 3 stores job state and reads `processing.json` and `candidates.json`.
5. Member 3 maps only successfully generated and approved preview files to safe `/media/{job_id}/...` URLs.
6. Member 3 returns the PRD result response schema without exposing internal filesystem paths.

## API endpoints

Do not rename or redesign these PRD routes:

- `POST /api/search`
- `POST /api/jobs`
- `GET /api/jobs/{job_id}`
- `GET /api/results/{job_id}`
- `GET /api/health`

## Error and partial-failure behavior

Member 2 pipeline statuses are `complete`, `partial` and `failed`.

Member 3 should preserve warnings separately from fatal errors.

When the alignment gate blocks a comparison:

- Return available epoch previews.
- Preserve the comparison's blocked status and processing explanation.
- Do not generate or return a misleading difference URL.
- Do not represent an incomplete comparison as a successful result.

When the pipeline returns `partial`, Member 3 should expose the successfully generated outputs while clearly communicating missing inputs and blocked comparisons.

Candidate records are preliminary and unverified. They must not be presented as confirmed astronomical discoveries.

## Security

Do not accept arbitrary filesystem paths from the browser.

The backend must derive media paths from the job directory, resolve paths safely and enforce that they remain within the allowed output root.

Never expose `source_file`, `aligned_fits` or absolute local filesystem paths in public API responses.

