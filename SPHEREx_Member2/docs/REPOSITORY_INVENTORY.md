# Repository and Handoff Inventory

## Supplied archive

`Planet-x-backend-handoff.zip` contains:
- 30 FITS cutouts under ZIP paths written with Windows backslash separators;
- `manifest.json` (46 observation records);
- `nasa_api.py`;
- `coordinate_validator.py`;
- `observation_summary_barnards_star.csv`;
- `observation_summary_epsilon_indi_babbs.csv`;
- `README.md`;
- `requirements.txt`.

The archive is a Member 1 handoff, not a complete shared SPHEREx Explorer repository. It does not contain Member 3's API service or Member 4's frontend.

## Existing Member 1 code

The Member 1 code was preserved under `input_handoff/`. It was inspected but not modified.

## Missing items

- 16 QR2 FITS cutouts referenced by manifest but absent from the ZIP.
- FITS cutouts for WISE 0855, RW Aurigae and R Draconis.
- Member 3 backend/API source files.
- Member 4 frontend source files.
- An existing agreed `docs/API_CONTRACT.md` from the full repository (this handoff supplies only the PRD API contract).

## File path note

The ZIP stores FITS paths using Windows backslashes. The Member 2 manifest resolver normalizes path separators and also checks `data/raw/<basename>`, without modifying the original manifest.
