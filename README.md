# Wisconsin Chloride Concentrations Map

Interactive map of chloride concentrations in Wisconsin lakes and rivers, sourced from the [EPA Water Quality Portal](https://www.waterqualitydata.us/).

## Features

- Toggle between **Most Recent**, **Mean**, and **Max** values per site
- Blue -> Red color bins (colorblind-friendly): 0–10 / 10–50 / 50–100 / 100–500 / 500+ mg/L
- Hover tooltip: site name + current value
- Click panel: most recent sample date, mean, max, sample count, time series

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
