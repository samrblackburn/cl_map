# Wisconsin Chloride Concentrations Map

Interactive map of chloride concentrations in Wisconsin lakes and rivers, sourced from the [EPA Water Quality Portal](https://www.waterqualitydata.us/).

## Features

- Toggle between **Most Recent**, **Mean**, and **Max** values per site
- Blue -> Red color bins (colorblind-friendly): 0–10 / 10–50 / 50–100 / 100–500 / 500+ mg/L
- Hover tooltip: site name + current value
- Click panel: most recent sample date, mean, max, sample count
- QA/QC samples removed; units harmonized to mg/L

## Setup

### 1. Install dependencies

```bash
pip install requests pandas
```

### 2. Fetch data from EPA WQP

```bash
python fetch_wqp_data.py
```

This will create `data/chloride_wi.json` (~1–5 MB). Re-run periodically to refresh.

> **Note:** The WQP request may take 1–5 minutes depending on server load.

### 3. Preview locally

```bash
# Python 3
python -m http.server 8000
# then open http://localhost:8000
```

> ⚠️ Must use a local HTTP server — browsers block `fetch()` on `file://` URLs.

## Deploy to GitHub Pages

1. Push the repo to GitHub (include `index.html`, `data/chloride_wi.json`, `fetch_wqp_data.py`)
2. Go to **Settings → Pages**
3. Set source to **Deploy from a branch → main → / (root)**
4. Your map will be live at `https://<username>.github.io/<repo>/`

### Keeping data fresh

Add a GitHub Actions workflow to re-fetch data on a schedule:

```yaml
# .github/workflows/refresh.yml
name: Refresh WQP Data
on:
  schedule:
    - cron: '0 6 1 * *'   # Monthly, 1st at 06:00 UTC
  workflow_dispatch:

jobs:
  fetch:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.12' }
      - run: pip install requests pandas
      - run: python fetch_wqp_data.py
      - uses: stefanzweifel/git-auto-commit-action@v5
        with:
          commit_message: "Auto-refresh WQP chloride data"
          file_pattern: data/chloride_wi.json
```

## Data notes

- **Source:** EPA Water Quality Portal, `characteristicName=Chloride`, `statecode=US:55`
- **QA/QC removal:** Activity types matching blank/replicate/spike/QC patterns excluded
- **Unit harmonization:** mg/L, µg/L, meq/L, mmol/L, ppm, ppb all converted to mg/L; unknown units dropped
- **Aggregation:** Per `MonitoringLocationIdentifier`; most recent/mean/max computed from all valid samples

## File structure

```
├── index.html            # Map application
├── fetch_wqp_data.py     # Data fetch + processing script
├── data/
│   └── chloride_wi.json  # Generated — not committed if using Actions
└── README.md
```
