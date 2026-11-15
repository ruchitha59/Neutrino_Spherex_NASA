# Manifest Contract

The Member 2 reader consumes Member 1's existing `manifest.json` without requiring a schema migration. The supplied handoff uses a root JSON object with `project`, `observations` and `last_updated_utc`; each observation includes product ID, target identifier, collection, band, wavelength bounds, UTC start/end, requested center, cutout size, archive URL, local path, download status and error message.

Member 2 validates the fields actually present. It accepts `product_id` or `observation_id`/`obs_id`, `infrared_band` or `band`, `access_url` or `source_url`, `observation_start_utc` or `obs_time`, and `local_file_path` or `local_fits`.

Windows path separators are normalized during lookup. The original manifest is never rewritten. A local file is considered present only when it exists on disk; `download_status="downloaded"` alone is not treated as proof.

Repeated observation IDs can legitimately occur for different detector bands. Exact duplicate detection uses the combination of product ID, collection, band and source URL.
