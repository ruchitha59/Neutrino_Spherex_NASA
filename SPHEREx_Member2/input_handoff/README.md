# Planet X – SPHEREx Backend

## Overview
This backend searches NASA/IPAC IRSA for SPHEREx observations and downloads FITS cutouts for a selected sky region.

## Requirements
- Python 3
- Packages listed in `requirements.txt`

## Setup Instructions

### 1. Open the project folder
Open the `Planet-x-backend` folder in VS Code.

### 2. Create a virtual environment
Run this command in the terminal:

```bash
python -m venv .venv
```

### 3. Activate the virtual environment

**Windows Command Prompt (CMD):**
```cmd
.venv\Scripts\activate.bat
```

**Windows PowerShell:**
```powershell
.venv\Scripts\Activate.ps1
```

Once activated, you should see `(.venv)` in your terminal.

### 4. Install the required packages

```bash
pip install -r requirements.txt
```

### 5. Run the backend

```bash
python nasa_api.py
```

Follow the prompts to enter Right Ascension (RA), Declination (Dec), and search radius.

## Project Files
- `nasa_api.py` – SPHEREx data search and FITS downloads
- `coordinate_validator.py` – Validates RA and Dec coordinates
- `observation_summary.csv` – Observation metadata
- `manifest.json` – Download records
- `cutouts/` – Downloaded FITS files
- `requirements.txt` – Required Python packages

**Note:** Each team member should create their own virtual environment. The `.venv` folder does not need to be shared.
