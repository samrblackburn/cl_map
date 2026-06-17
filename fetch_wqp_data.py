#!/usr/bin/env python3
"""
fetch_wqp_data.py
-----------------
Fetches chloride concentration data for Wisconsin from the EPA Water Quality
Portal (WQP), cleans and harmonizes units, removes QA/QC samples, aggregates
per site (most recent / mean / max), and writes data/chloride_wi.json.

Usage:
    python fetch_wqp_data.py

Output:
    data/chloride_wi.json

Requirements:
    pip install requests pandas
"""

import json
import os
import sys

import pandas as pd
import requests

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

WQP_RESULT_URL = "https://www.waterqualitydata.us/data/Result/search"
WQP_STATION_URL = "https://www.waterqualitydata.us/data/Station/search"

PARAMS_BASE = {
    "statecode": "US:55",  # Wisconsin FIPS
    "characteristicName": "Chloride",
    "dataProfile": "resultPhysChem",
    "mimeType": "csv",
    "zip": "no",
}

OUTPUT_DIR = "data"
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "chloride_wi.json")

# ---------------------------------------------------------------------------
# QA/QC exclusion patterns
# Applied to ActivityTypeCode — anything that looks like a QC replicate,
# blank, spike, or reference material is excluded.
# ---------------------------------------------------------------------------

QAQC_ACTIVITY_TYPES = {
    "Quality Control Sample-Field Blank",
    "Quality Control Sample-Equipment Blank",
    "Quality Control Sample-Lab Blank",
    "Quality Control Sample-Field Replicate",
    "Quality Control Sample-Lab Replicate",
    "Quality Control Sample-Field Spike",
    "Quality Control Sample-Lab Spike",
    "Quality Control Sample-Reference Material",
    "Quality Control-Calibration Check",
    "Quality Control-Meter Lab Blank",
    "Quality Control-Meter Lab Duplicate",
    "Quality Control-Meter Field Blank",
    "Quality Control-Meter Field Duplicate",
    "Quality Control-Blind Sample",
    "Quality Control-Inter-lab/agency",
    "Quality Control-Inter-lab Split",
    "Quality Control-Sample-Lab Spike",
    "Quality Control Field Sample Replicate",
    "Quality Control Field Blank",
}

# ---------------------------------------------------------------------------
# Unit conversion to mg/L
# ---------------------------------------------------------------------------

UNIT_CONVERSIONS = {
    "mg/l": 1.0,
    "mg/L": 1.0,
    "mg/l as cl": 1.0,
    "mg/L as Cl": 1.0,
    "ug/l": 0.001,
    "ug/L": 0.001,
    "µg/l": 0.001,
    "µg/L": 0.001,
    "ppb": 0.001,
    "ppm": 1.0,
    "meq/l": 35.453,  # chloride molar mass
    "meq/L": 35.453,
    "umol/l": 0.035453,
    "umol/L": 0.035453,
    "mmol/l": 35.453,
    "mmol/L": 35.453,
    "g/l": 1000.0,
    "g/L": 1000.0,
    "mg/kg": 1.0,  # approximate for water (density ~1)
    "mg/kg as cl": 1.0,
    "mg/kg as Cl": 1.0,
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def fetch_csv(url: str, params: dict, label: str) -> pd.DataFrame:
    """Stream a CSV from the WQP and return a DataFrame."""
    print(f"  Requesting {label} from WQP...", flush=True)
    resp = requests.get(url, params=params, stream=True, timeout=300)
    resp.raise_for_status()
    from io import StringIO

    content = resp.content.decode("utf-8", errors="replace")
    # WQP sometimes returns an HTML error page
    if content.strip().startswith("<"):
        print("  ERROR: WQP returned HTML instead of CSV. Check parameters.")
        print(content[:500])
        sys.exit(1)
    df = pd.read_csv(StringIO(content), dtype=str, low_memory=False)
    print(f"  Received {len(df):,} rows.")
    return df


def to_float(val):
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def convert_to_mg_l(value: float, unit: str) -> float | None:
    """Convert a value to mg/L using the known unit map."""
    if value is None:
        return None
    unit_clean = str(unit).strip()
    factor = UNIT_CONVERSIONS.get(unit_clean)
    if factor is None:
        # Try case-insensitive lookup
        for k, v in UNIT_CONVERSIONS.items():
            if k.lower() == unit_clean.lower():
                factor = v
                break
    if factor is None:
        return None  # Unknown unit — drop rather than guess
    return value * factor


def safe_date(val) -> str | None:
    if pd.isna(val) or str(val).strip() in ("", "nan", "NaT"):
        return None
    return str(val).strip()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # ------------------------------------------------------------------
    # 1. Fetch result data
    # ------------------------------------------------------------------
    results_df = fetch_csv(WQP_RESULT_URL, PARAMS_BASE, "Result data")

    print(f"\nColumns available: {list(results_df.columns[:20])} ...")

    # ------------------------------------------------------------------
    # 2. Fetch station (site) data for lat/lon
    # ------------------------------------------------------------------
    station_params = {
        "statecode": "US:55",
        "characteristicName": "Chloride",
        "mimeType": "csv",
        "zip": "no",
    }
    stations_df = fetch_csv(WQP_STATION_URL, station_params, "Station data")

    # ------------------------------------------------------------------
    # 3. Remove QA/QC samples
    # ------------------------------------------------------------------
    before = len(results_df)
    if "ActivityTypeCode" in results_df.columns:
        results_df = results_df[
            ~results_df["ActivityTypeCode"].isin(QAQC_ACTIVITY_TYPES)
        ]
    # Also drop any row where ActivityIdentifier contains common QC flags
    if "ActivityIdentifier" in results_df.columns:
        qc_pattern = (
            r"(?i)(blank|replicate|spike|qc|qaqc|dup\b|duplicate|reference material)"
        )
        results_df = results_df[
            ~results_df["ActivityIdentifier"].str.contains(
                qc_pattern, na=False, regex=True
            )
        ]
    print(f"\nQA/QC removal: {before:,} → {len(results_df):,} rows retained.")

    # ------------------------------------------------------------------
    # 4. Extract and harmonize values
    # ------------------------------------------------------------------
    # Key columns (WQP naming convention)
    COL_SITE = "MonitoringLocationIdentifier"
    COL_VAL = "ResultMeasureValue"
    COL_UNIT = "ResultMeasure/MeasureUnitCode"
    COL_DATE = "ActivityStartDate"
    COL_NAME = "MonitoringLocationName"  # may not be in results; we'll join

    needed = [COL_SITE, COL_VAL, COL_UNIT, COL_DATE]
    for c in needed:
        if c not in results_df.columns:
            print(f"  WARNING: expected column '{c}' not found.")

    df = results_df[[c for c in needed if c in results_df.columns]].copy()

    df["value_raw"] = df[COL_VAL].apply(to_float)
    df["value_mgl"] = df.apply(
        lambda r: convert_to_mg_l(r["value_raw"], r.get(COL_UNIT, "")),
        axis=1,
    )

    # Drop rows with no usable value
    n_before = len(df)
    df = df.dropna(subset=["value_mgl"])
    # Drop physically impossible values (negative or extreme outliers > 500,000 mg/L)
    df = df[(df["value_mgl"] >= 0) & (df["value_mgl"] <= 500_000)]
    print(
        f"Value harmonization: {n_before:,} → {len(df):,} rows with valid mg/L values."
    )

    # ------------------------------------------------------------------
    # 5. Merge station info (lat/lon, site name)
    # ------------------------------------------------------------------
    STAT_SITE = "MonitoringLocationIdentifier"
    STAT_LAT = "LatitudeMeasure"
    STAT_LON = "LongitudeMeasure"
    STAT_NAME = "MonitoringLocationName"
    STAT_TYPE = "MonitoringLocationTypeName"

    keep_stat = [
        c
        for c in [STAT_SITE, STAT_LAT, STAT_LON, STAT_NAME, STAT_TYPE]
        if c in stations_df.columns
    ]
    stations_slim = stations_df[keep_stat].drop_duplicates(subset=[STAT_SITE])

    df = df.merge(stations_slim, left_on=COL_SITE, right_on=STAT_SITE, how="left")

    df["lat"] = df[STAT_LAT].apply(to_float)
    df["lon"] = df[STAT_LON].apply(to_float)

    # Drop rows without coordinates
    df = df.dropna(subset=["lat", "lon"])
    # Basic bounds check — Wisconsin roughly 42–47 N, 86–93 W
    df = df[
        (df["lat"] >= 40) & (df["lat"] <= 49) & (df["lon"] >= -98) & (df["lon"] <= -82)
    ]
    print(f"After coordinate filtering: {len(df):,} rows.")

    # ------------------------------------------------------------------
    # 6. Parse dates and sort
    # ------------------------------------------------------------------
    df["date"] = pd.to_datetime(df[COL_DATE], errors="coerce")
    df = df.dropna(subset=["date"])
    df = df.sort_values("date")

    # ------------------------------------------------------------------
    # 7. Aggregate per site
    # ------------------------------------------------------------------
    site_col = COL_SITE

    def agg_site(grp):
        vals = grp["value_mgl"]
        dates = grp["date"]

        most_recent_idx = dates.idxmax()
        max_idx = vals.idxmax()

        return pd.Series(
            {
                "lat": grp["lat"].iloc[0],
                "lon": grp["lon"].iloc[0],
                "site_name": grp[STAT_NAME].iloc[0] if STAT_NAME in grp.columns else "",
                "site_type": grp[STAT_TYPE].iloc[0] if STAT_TYPE in grp.columns else "",
                "n_samples": len(vals),
                "recent_value": round(grp.loc[most_recent_idx, "value_mgl"], 3),
                "recent_date": grp.loc[most_recent_idx, "date"].strftime("%Y-%m-%d"),
                "mean_value": round(float(vals.mean()), 3),
                "max_value": round(float(vals.max()), 3),
                "max_date": grp.loc[max_idx, "date"].strftime("%Y-%m-%d"),
            }
        )

    print("\nAggregating per site...")
    sites = df.groupby(site_col, sort=False).apply(agg_site).reset_index()
    sites = sites.rename(columns={site_col: "site_id"})

    print(f"Total unique sites: {len(sites):,}")

    # ------------------------------------------------------------------
    # 8. Build output JSON
    # ------------------------------------------------------------------
    # Separate sites with only 1 sample (no mean/max variance to show)
    records = []
    for _, row in sites.iterrows():
        record = {
            "id": row["site_id"],
            "name": str(row["site_name"]) if row["site_name"] else row["site_id"],
            "type": str(row["site_type"]),
            "lat": row["lat"],
            "lon": row["lon"],
            "n": int(row["n_samples"]),
            "recent_val": row["recent_value"],
            "recent_date": row["recent_date"],
            "mean_val": row["mean_value"],
            "max_val": row["max_value"],
            "max_date": row["max_date"],
        }
        records.append(record)

    output = {
        "generated": pd.Timestamp.now().isoformat(timespec="seconds"),
        "source": "EPA Water Quality Portal — characteristicName=Chloride, statecode=US:55",
        "units": "mg/L",
        "n_sites": len(records),
        "sites": records,
    }

    with open(OUTPUT_FILE, "w") as f:
        json.dump(output, f, separators=(",", ":"))

    size_kb = os.path.getsize(OUTPUT_FILE) / 1024
    print(f"\n✓ Wrote {OUTPUT_FILE} ({size_kb:.1f} KB, {len(records):,} sites)")
    print(
        "  Run the map by opening index.html in your browser or deploying to GitHub Pages."
    )


if __name__ == "__main__":
    main()
