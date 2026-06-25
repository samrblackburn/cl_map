# Minnesota & Wisconsin Chloride Concentrations Map

Interactive map of chloride concentrations in Minnesota & Wisconsin waters, sourced from the [EPA Water Quality Portal](https://www.waterqualitydata.us/).


## Data notes

- **Source:** EPA Water Quality Portal, `characteristicName=Chloride`, `statecode=US:55|US:27`
- **QA/QC removal:** Activity types matching blank/replicate/spike/QC patterns excluded
- **Unit harmonization:** mg/L, µg/L, meq/L, mmol/L, ppm, ppb all converted to mg/L; unknown units dropped
- **Aggregation:** Per `MonitoringLocationIdentifier`; most recent/mean/max computed from all valid samples
- **Cleaning** Remove values below zero or greater than 20,000 mg/L.

## File structure

```
├── index.html            # Map application
├── fetch_wqp_data.py     # Data fetch + processing script
├── data/
│   └── chloride_wi.json  # Generated — not committed if using Actions
└── README.md
```
