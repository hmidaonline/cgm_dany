#!/usr/bin/env python3
"""
GlycoView – Database Inspection Script (Étape 0)

Connects to the Nightscout MongoDB in READ-ONLY mode and produces a
comprehensive data quality report at docs/data_report.md.

Schema reference:
    nightscout/cgm-remote-monitor (AGPL-3.0)
    - lib/data/ddata.js              → data model & deduplication logic
    - lib/data/dataloader.js         → MongoDB query patterns
    - lib/plugins/iob.js             → IOB from devicestatus.openaps.iob
    - lib/plugins/cob.js             → COB from devicestatus.openaps.suggested/enacted
    - lib/plugins/openaps.js         → prediction lines (predBGs: IOB/COB/UAM/ZT)
    - lib/client-core/devicestatus/openaps.js → devicestatus shape extraction
    - tests/fixtures/aaps-single-doc.js       → canonical AAPS document shapes

NO DATA IS WRITTEN to MongoDB. All operations are find() / aggregate().

Usage:
    cp .env.example .env   # fill in MONGODB_URI
    pip install pymongo python-dotenv pandas tabulate
    python scripts/inspect_db.py
"""

from __future__ import annotations

import json
import os
import sys
import textwrap
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
from dotenv import load_dotenv
from pymongo import MongoClient, ReadPreference
from pymongo.errors import OperationFailure
from tabulate import tabulate

# ──────────────────────────────────────────────
# CONFIG
# ──────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017/nightscout")
MONGODB_DATABASE = os.getenv("MONGODB_DATABASE", "nightscout")
OUTPUT_PATH = PROJECT_ROOT / "docs" / "data_report.md"

# Collections we care about
EXPECTED_COLLECTIONS = ["entries", "treatments", "devicestatus", "profile"]

# ──────────────────────────────────────────────
# HELPERS
# ──────────────────────────────────────────────

def connect_readonly() -> tuple[MongoClient, Any]:
    """Connect to MongoDB with secondary-preferred read preference."""
    client = MongoClient(
        MONGODB_URI,
        read_preference=ReadPreference.SECONDARY_PREFERRED,
        appname="glycoview-inspector",
        serverSelectionTimeoutMS=10_000,
    )
    db = client[MONGODB_DATABASE]
    # Verify connection
    db.command("ping")
    print(f"Connected to {MONGODB_DATABASE}")
    return client, db


def safe_sample(collection, n: int = 5) -> list[dict]:
    """Return n sample documents, handling empty collections."""
    try:
        return list(collection.find().sort("_id", -1).limit(n))
    except OperationFailure:
        return list(collection.find().limit(n))


def infer_field_types(docs: list[dict], prefix: str = "") -> dict[str, Counter]:
    """Recursively infer field names and their Python types from sample documents."""
    field_types: dict[str, Counter] = defaultdict(Counter)
    for doc in docs:
        _recurse_fields(doc, prefix, field_types)
    return dict(field_types)


def _recurse_fields(obj: Any, prefix: str, acc: dict[str, Counter], depth: int = 0):
    if depth > 6:
        return
    if isinstance(obj, dict):
        for key, val in obj.items():
            full_key = f"{prefix}.{key}" if prefix else key
            type_name = type(val).__name__
            if isinstance(val, datetime):
                type_name = "datetime"
            elif isinstance(val, (int, float)):
                type_name = "number"
            elif isinstance(val, str):
                type_name = "string"
            elif isinstance(val, bool):
                type_name = "boolean"
            elif isinstance(val, list):
                type_name = "array"
            elif isinstance(val, dict):
                type_name = "object"
            elif val is None:
                type_name = "null"
            acc[full_key][type_name] += 1
            if isinstance(val, dict):
                _recurse_fields(val, full_key, acc, depth + 1)
            elif isinstance(val, list) and val:
                # Sample first element of arrays
                _recurse_fields(val[0], f"{full_key}[]", acc, depth + 1)


def detect_date_range(collection, date_field: str) -> tuple[str, str] | None:
    """Find min and max of a date field using aggregation."""
    try:
        pipeline = [
            {"$group": {
                "_id": None,
                "min_date": {"$min": f"${date_field}"},
                "max_date": {"$max": f"${date_field}"},
            }}
        ]
        result = list(collection.aggregate(pipeline))
        if result:
            r = result[0]
            min_d = r["min_date"]
            max_d = r["max_date"]
            # Normalize to string
            fmt = lambda d: d.isoformat() if isinstance(d, datetime) else str(d)
            return fmt(min_d), fmt(max_d)
    except Exception as e:
        print(f"  Warning: Could not detect date range for {date_field}: {e}")
    return None


def count_duplicates_entries(collection) -> dict:
    """Detect duplicate entries based on (date, sgv) pair."""
    try:
        pipeline = [
            {"$match": {"type": "sgv"}},
            {"$group": {
                "_id": {"date": "$date", "sgv": "$sgv"},
                "count": {"$sum": 1},
            }},
            {"$match": {"count": {"$gt": 1}}},
            {"$count": "duplicate_groups"},
        ]
        result = list(collection.aggregate(pipeline))
        return {"duplicate_groups": result[0]["duplicate_groups"] if result else 0}
    except Exception as e:
        return {"error": str(e)}


def count_duplicates_treatments(collection) -> dict:
    """Detect duplicate treatments based on (created_at, eventType)."""
    try:
        pipeline = [
            {"$group": {
                "_id": {"created_at": "$created_at", "eventType": "$eventType"},
                "count": {"$sum": 1},
            }},
            {"$match": {"count": {"$gt": 1}}},
            {"$count": "duplicate_groups"},
        ]
        result = list(collection.aggregate(pipeline))
        return {"duplicate_groups": result[0]["duplicate_groups"] if result else 0}
    except Exception as e:
        return {"error": str(e)}


def analyze_sgv_gaps(collection, sample_size: int = 50_000) -> dict:
    """Analyze gaps in SGV readings (expected every 5 min)."""
    try:
        pipeline = [
            {"$match": {"type": "sgv", "date": {"$exists": True}}},
            {"$sort": {"date": -1}},
            {"$limit": sample_size},
            {"$project": {"date": 1}},
        ]
        docs = list(collection.aggregate(pipeline))
        if len(docs) < 2:
            return {"status": "insufficient data"}

        dates = sorted([d["date"] for d in docs if isinstance(d.get("date"), (int, float))])
        if not dates:
            return {"status": "no numeric dates found"}

        # Compute gaps in minutes
        gaps = [(dates[i + 1] - dates[i]) / 60_000 for i in range(len(dates) - 1)]
        gaps_series = pd.Series(gaps)

        expected_interval = 5.0  # minutes
        gap_threshold = 15.0  # >15 min = a "hole"
        large_gaps = gaps_series[gaps_series > gap_threshold]

        return {
            "total_readings_sampled": len(dates),
            "period_hours": round((dates[-1] - dates[0]) / 3_600_000, 1),
            "median_interval_min": round(gaps_series.median(), 2),
            "mean_interval_min": round(gaps_series.mean(), 2),
            "max_gap_min": round(gaps_series.max(), 1),
            "gaps_over_15min": int(len(large_gaps)),
            "gaps_over_30min": int(len(gaps_series[gaps_series > 30])),
            "gaps_over_60min": int(len(gaps_series[gaps_series > 60])),
            "pct_expected_5min": round(
                (gaps_series.between(4, 6).sum() / len(gaps_series)) * 100, 1
            ),
        }
    except Exception as e:
        return {"error": str(e)}


def analyze_sgv_outliers(collection) -> dict:
    """Detect outlier SGV values (too low or too high to be realistic)."""
    try:
        pipeline = [
            {"$match": {"type": "sgv", "sgv": {"$exists": True}}},
            {"$group": {
                "_id": None,
                "count": {"$sum": 1},
                "min_sgv": {"$min": "$sgv"},
                "max_sgv": {"$max": "$sgv"},
                "avg_sgv": {"$avg": "$sgv"},
                "below_20": {"$sum": {"$cond": [{"$lt": ["$sgv", 20]}, 1, 0]}},
                "above_500": {"$sum": {"$cond": [{"$gt": ["$sgv", 500]}, 1, 0]}},
            }},
        ]
        result = list(collection.aggregate(pipeline))
        if result:
            r = result[0]
            return {
                "total_sgv": r["count"],
                "min": r["min_sgv"],
                "max": r["max_sgv"],
                "mean": round(r["avg_sgv"], 1),
                "below_20_count": r["below_20"],
                "above_500_count": r["above_500"],
            }
        return {"status": "no SGV data"}
    except Exception as e:
        return {"error": str(e)}


def get_event_types(collection) -> list[tuple[str, int]]:
    """Get all eventType values and their counts from treatments."""
    try:
        pipeline = [
            {"$group": {"_id": "$eventType", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
        ]
        result = list(collection.aggregate(pipeline))
        return [(r["_id"], r["count"]) for r in result]
    except Exception as e:
        return [("error", str(e))]


def analyze_devicestatus_structure(collection) -> dict:
    """Analyze the structure of devicestatus documents (openaps/pump/uploader)."""
    sample = safe_sample(collection, 20)
    if not sample:
        return {"status": "empty collection"}

    has_openaps = sum(1 for d in sample if "openaps" in d)
    has_pump = sum(1 for d in sample if "pump" in d)
    has_uploader = sum(1 for d in sample if "uploader" in d or "uploaderBattery" in d)
    has_loop = sum(1 for d in sample if "loop" in d)
    has_configuration = sum(1 for d in sample if "configuration" in d)

    # Dig into openaps structure
    openaps_fields = set()
    openaps_suggested_fields = set()
    openaps_enacted_fields = set()
    openaps_iob_fields = set()
    pred_bg_keys = set()

    for d in sample:
        if "openaps" in d and isinstance(d["openaps"], dict):
            openaps_fields.update(d["openaps"].keys())
            if "suggested" in d["openaps"] and isinstance(d["openaps"]["suggested"], dict):
                openaps_suggested_fields.update(d["openaps"]["suggested"].keys())
                if "predBGs" in d["openaps"]["suggested"] and isinstance(d["openaps"]["suggested"]["predBGs"], dict):
                    pred_bg_keys.update(d["openaps"]["suggested"]["predBGs"].keys())
            if "enacted" in d["openaps"] and isinstance(d["openaps"]["enacted"], dict):
                openaps_enacted_fields.update(d["openaps"]["enacted"].keys())
                if "predBGs" in d["openaps"]["enacted"] and isinstance(d["openaps"]["enacted"]["predBGs"], dict):
                    pred_bg_keys.update(d["openaps"]["enacted"]["predBGs"].keys())
            if "iob" in d["openaps"]:
                iob_val = d["openaps"]["iob"]
                if isinstance(iob_val, list) and iob_val:
                    iob_val = iob_val[0]
                if isinstance(iob_val, dict):
                    openaps_iob_fields.update(iob_val.keys())

    # Pump structure
    pump_fields = set()
    for d in sample:
        if "pump" in d and isinstance(d["pump"], dict):
            pump_fields.update(d["pump"].keys())

    return {
        "sample_size": len(sample),
        "has_openaps": f"{has_openaps}/{len(sample)}",
        "has_pump": f"{has_pump}/{len(sample)}",
        "has_uploader": f"{has_uploader}/{len(sample)}",
        "has_loop": f"{has_loop}/{len(sample)}",
        "has_configuration": f"{has_configuration}/{len(sample)}",
        "openaps_top_keys": sorted(openaps_fields),
        "openaps_suggested_keys": sorted(openaps_suggested_fields),
        "openaps_enacted_keys": sorted(openaps_enacted_fields),
        "openaps_iob_keys": sorted(openaps_iob_fields),
        "predBG_types": sorted(pred_bg_keys),
        "pump_keys": sorted(pump_fields),
    }


def analyze_profile(collection) -> dict:
    """Analyze the profile collection structure."""
    sample = safe_sample(collection, 5)
    if not sample:
        return {"status": "empty collection"}

    result = {"count": len(sample)}

    for doc in sample[:1]:  # Analyze first profile
        if "store" in doc and isinstance(doc["store"], dict):
            profiles = list(doc["store"].keys())
            result["profile_names"] = profiles
            # Look at first profile
            if profiles:
                p = doc["store"][profiles[0]]
                if isinstance(p, dict):
                    result["profile_fields"] = sorted(p.keys())
                    # Check for time-varying arrays
                    for key in ["basal", "carbratio", "sens", "target_low", "target_high"]:
                        if key in p and isinstance(p[key], list):
                            result[f"{key}_segments"] = len(p[key])
                    if "dia" in p:
                        result["dia"] = p["dia"]
                    if "units" in p:
                        result["units"] = p["units"]
                    if "timezone" in p:
                        result["timezone"] = p["timezone"]
        if "defaultProfile" in doc:
            result["defaultProfile"] = doc["defaultProfile"]
        if "startDate" in doc:
            result["startDate"] = str(doc["startDate"])

    return result


# ──────────────────────────────────────────────
# MAIN INSPECTION
# ──────────────────────────────────────────────

def main():
    print("=" * 60)
    print("GlycoView – Database Inspector")
    print("=" * 60)

    client, db = connect_readonly()

    report_sections: list[str] = []
    report_sections.append("# GlycoView – Data Quality Report\n")
    report_sections.append(f"Generated: {datetime.now(timezone.utc).isoformat()}\n")
    report_sections.append(f"Database: `{MONGODB_DATABASE}`\n")

    # ── 1. List all collections ──
    print("\n📋 Listing collections...")
    all_collections = db.list_collection_names()
    print(f"  Found {len(all_collections)} collections: {all_collections}")

    report_sections.append("## 1. Collections\n")
    coll_rows = []
    for name in sorted(all_collections):
        try:
            count = db[name].estimated_document_count()
        except Exception:
            count = "?"
        coll_rows.append([name, count, "✓" if name in EXPECTED_COLLECTIONS else ""])
    report_sections.append(tabulate(coll_rows, headers=["Collection", "Documents", "Expected"], tablefmt="github"))
    report_sections.append("")

    # ── 2. Entries analysis ──
    print("\n📊 Analyzing entries...")
    if "entries" in all_collections:
        entries_col = db["entries"]
        count = entries_col.estimated_document_count()
        print(f"  {count} documents")

        report_sections.append("## 2. Entries (CGM readings)\n")
        report_sections.append(f"**Total documents:** {count:,}\n")

        # Date range
        for field in ["date", "dateString", "sysTime"]:
            dr = detect_date_range(entries_col, field)
            if dr:
                report_sections.append(f"**Date range** (`{field}`): `{dr[0]}` → `{dr[1]}`\n")
                break

        # Fields & types
        sample = safe_sample(entries_col, 50)
        ft = infer_field_types(sample)
        ft_rows = [[k, ", ".join(f"{t}({c})" for t, c in v.items())] for k, v in sorted(ft.items())]
        report_sections.append("### Fields and Types\n")
        report_sections.append(tabulate(ft_rows, headers=["Field", "Types (count)"], tablefmt="github"))
        report_sections.append("")

        # SGV outliers
        outliers = analyze_sgv_outliers(entries_col)
        report_sections.append("### SGV Value Distribution\n")
        report_sections.append(f"```json\n{json.dumps(outliers, indent=2)}\n```\n")

        # Gaps
        gaps = analyze_sgv_gaps(entries_col)
        report_sections.append("### Data Gaps (CGM)\n")
        report_sections.append(f"```json\n{json.dumps(gaps, indent=2)}\n```\n")

        # Duplicates
        dupes = count_duplicates_entries(entries_col)
        report_sections.append("### Duplicates\n")
        report_sections.append(f"Duplicate (date, sgv) groups: **{dupes.get('duplicate_groups', 'N/A')}**\n")

        # Direction values
        try:
            dir_pipeline = [
                {"$match": {"type": "sgv"}},
                {"$group": {"_id": "$direction", "count": {"$sum": 1}}},
                {"$sort": {"count": -1}},
            ]
            directions = list(entries_col.aggregate(dir_pipeline))
            dir_rows = [[d["_id"], d["count"]] for d in directions]
            report_sections.append("### Direction Values\n")
            report_sections.append(tabulate(dir_rows, headers=["Direction", "Count"], tablefmt="github"))
            report_sections.append("")
        except Exception:
            pass

    # ── 3. Treatments analysis ──
    print("\n💉 Analyzing treatments...")
    if "treatments" in all_collections:
        treatments_col = db["treatments"]
        count = treatments_col.estimated_document_count()
        print(f"  {count} documents")

        report_sections.append("## 3. Treatments\n")
        report_sections.append(f"**Total documents:** {count:,}\n")

        # Date range
        dr = detect_date_range(treatments_col, "created_at")
        if dr:
            report_sections.append(f"**Date range** (`created_at`): `{dr[0]}` → `{dr[1]}`\n")

        # Event types
        event_types = get_event_types(treatments_col)
        report_sections.append("### Event Types\n")
        et_rows = [[et, c] for et, c in event_types]
        report_sections.append(tabulate(et_rows, headers=["eventType", "Count"], tablefmt="github"))
        report_sections.append("")

        # Fields & types
        sample = safe_sample(treatments_col, 50)
        ft = infer_field_types(sample)
        ft_rows = [[k, ", ".join(f"{t}({c})" for t, c in v.items())] for k, v in sorted(ft.items())]
        report_sections.append("### Fields and Types\n")
        report_sections.append(tabulate(ft_rows, headers=["Field", "Types (count)"], tablefmt="github"))
        report_sections.append("")

        # Duplicates
        dupes = count_duplicates_treatments(treatments_col)
        report_sections.append("### Duplicates\n")
        report_sections.append(f"Duplicate (created_at, eventType) groups: **{dupes.get('duplicate_groups', 'N/A')}**\n")

    # ── 4. Device Status analysis ──
    print("\n📱 Analyzing devicestatus...")
    if "devicestatus" in all_collections:
        ds_col = db["devicestatus"]
        count = ds_col.estimated_document_count()
        print(f"  {count} documents")

        report_sections.append("## 4. Device Status\n")
        report_sections.append(f"**Total documents:** {count:,}\n")

        dr = detect_date_range(ds_col, "created_at")
        if dr:
            report_sections.append(f"**Date range** (`created_at`): `{dr[0]}` → `{dr[1]}`\n")

        # Structure analysis
        ds_structure = analyze_devicestatus_structure(ds_col)
        report_sections.append("### Structure Analysis\n")
        report_sections.append(f"```json\n{json.dumps(ds_structure, indent=2, default=str)}\n```\n")

        # Full field inventory from larger sample
        sample = safe_sample(ds_col, 30)
        ft = infer_field_types(sample)
        ft_rows = [[k, ", ".join(f"{t}({c})" for t, c in v.items())] for k, v in sorted(ft.items()) if k.count(".") < 3]
        report_sections.append("### Fields and Types (top 3 levels)\n")
        report_sections.append(tabulate(ft_rows, headers=["Field", "Types (count)"], tablefmt="github"))
        report_sections.append("")

        # Device types
        try:
            dev_pipeline = [
                {"$group": {"_id": "$device", "count": {"$sum": 1}}},
                {"$sort": {"count": -1}},
                {"$limit": 20},
            ]
            devices = list(ds_col.aggregate(dev_pipeline))
            dev_rows = [[d["_id"], d["count"]] for d in devices]
            report_sections.append("### Devices\n")
            report_sections.append(tabulate(dev_rows, headers=["Device", "Count"], tablefmt="github"))
            report_sections.append("")
        except Exception:
            pass

    # ── 5. Profile analysis ──
    print("\n👤 Analyzing profile...")
    if "profile" in all_collections:
        profile_col = db["profile"]
        count = profile_col.estimated_document_count()
        print(f"  {count} documents")

        report_sections.append("## 5. Profile\n")
        report_sections.append(f"**Total documents:** {count:,}\n")

        profile_info = analyze_profile(profile_col)
        report_sections.append("### Profile Structure\n")
        report_sections.append(f"```json\n{json.dumps(profile_info, indent=2, default=str)}\n```\n")

    # ── 6. Summary & Recommendations ──
    report_sections.append("## 6. Summary & Data Quality Assessment\n")
    report_sections.append("### Key Findings\n")
    report_sections.append(textwrap.dedent("""\
    - **Collections found:** Listed above with document counts
    - **SGV data quality:** See gaps analysis and outlier detection above
    - **Duplicates:** Checked for both entries and treatments
    - **Device status:** Structure analysis shows available AAPS/OpenAPS data
    - **Predictions available:** Check predBG_types in devicestatus for IOB/COB/UAM/ZT prediction lines
    
    ### Recommendations for Pipeline
    
    1. **Deduplication:** Implement dedup on `(date, sgv)` for entries and `(created_at, eventType)` for treatments
    2. **Gap handling:** Interpolate gaps < 30 min, flag gaps > 30 min as data quality issues
    3. **Outlier filtering:** Remove SGV < 20 or > 500 mg/dL (sensor errors)
    4. **Timezone:** Store timestamps in UTC, convert to `Africa/Casablanca` for display
    5. **Date fields:** Use `date` (epoch ms) for entries, `created_at` (ISO string) for treatments/devicestatus
    """))

    # ── 7. Schema reference ──
    report_sections.append("## 7. Nightscout Schema Reference\n")
    report_sections.append(textwrap.dedent("""\
    > Source: nightscout/cgm-remote-monitor (AGPL-3.0)
    > Files consulted:
    > - `lib/data/ddata.js` – data model, dedup logic
    > - `lib/data/dataloader.js` – MongoDB queries, field normalization
    > - `lib/plugins/iob.js` – IOB calculation from devicestatus.openaps.iob
    > - `lib/plugins/cob.js` – COB from devicestatus.openaps.suggested/enacted
    > - `lib/plugins/openaps.js` – AAPS loop status and prediction lines
    > - `lib/client-core/devicestatus/openaps.js` – devicestatus shape extraction
    > - `lib/profilefunctions.js` – profile data model
    > - `tests/fixtures/aaps-single-doc.js` – canonical AAPS document shapes
    
    ### entries
    | Field | Type | Description |
    |-------|------|-------------|
    | `_id` | ObjectId | MongoDB ID |
    | `type` | string | `"sgv"`, `"mbg"`, or `"cal"` |
    | `sgv` | number | Sensor glucose value (mg/dL) |
    | `date` | number | Epoch milliseconds |
    | `dateString` | string | ISO 8601 timestamp |
    | `direction` | string | Trend arrow (Flat, FortyFiveUp, etc.) |
    | `device` | string | Source device |
    | `filtered` | number | Filtered raw value |
    | `unfiltered` | number | Unfiltered raw value |
    | `noise` | number | Noise level |
    | `rssi` | number | Signal strength |
    | `app` | string | Source app (e.g., "AAPS") |
    | `utcOffset` | number | UTC offset in minutes |
    
    ### treatments
    | Field | Type | Description |
    |-------|------|-------------|
    | `_id` | ObjectId | MongoDB ID |
    | `eventType` | string | Event type (see table above) |
    | `created_at` | string | ISO 8601 timestamp |
    | `insulin` | number | Bolus amount (U) |
    | `carbs` | number | Carbohydrates (g) |
    | `duration` | number | Duration (minutes) |
    | `rate` | number | Temp basal rate |
    | `absolute` | number | Absolute temp basal rate |
    | `percent` | number | Percentage change |
    | `profile` | string | Profile name (for Profile Switch) |
    | `targetTop` / `targetBottom` | number | Temp target values |
    | `isSMB` | boolean | Super Micro Bolus flag |
    | `enteredBy` | string | Source (e.g., "openaps://AndroidAPS") |
    
    ### devicestatus
    | Field | Type | Description |
    |-------|------|-------------|
    | `device` | string | Device URI |
    | `created_at` | string | ISO 8601 timestamp |
    | `openaps.suggested` | object | Algorithm suggestion (bg, eventualBG, COB, IOB, predBGs, reason, timestamp) |
    | `openaps.enacted` | object | Enacted changes (rate, duration, bg, predBGs, timestamp, recieved) |
    | `openaps.iob` | object | IOB state (iob, basaliob, activity, timestamp) |
    | `pump` | object | Pump state (reservoir, battery, status, clock, extended) |
    | `uploader` / `uploaderBattery` | object/number | Phone battery info |
    | `configuration` | object | AAPS config (pump, version, insulin, aps, sensitivity) |
    
    ### profile
    | Field | Type | Description |
    |-------|------|-------------|
    | `defaultProfile` | string | Name of the default profile |
    | `startDate` | string | Profile activation date |
    | `store` | object | Map of profile name → profile data |
    | `store.*.dia` | number | Duration of Insulin Action (hours) |
    | `store.*.carbratio` | array | Carb ratio schedule [{time, value}] |
    | `store.*.sens` | array | Insulin sensitivity schedule [{time, value}] |
    | `store.*.basal` | array | Basal rate schedule [{time, value}] |
    | `store.*.target_low` / `target_high` | array | Target range schedule |
    | `store.*.timezone` | string | IANA timezone |
    | `store.*.units` | string | "mg/dl" or "mmol" |
    """))

    # ── Write report ──
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    report_text = "\n".join(report_sections)
    OUTPUT_PATH.write_text(report_text, encoding="utf-8")
    print(f"\n✅ Report written to {OUTPUT_PATH}")
    print(f"   ({len(report_text):,} chars)")

    client.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
