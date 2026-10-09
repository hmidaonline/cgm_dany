# GlycoView – Data Quality Report

Generated: 2026-10-09T09:38:28.375759+00:00

Database: `nightscout`

## 1. Collections

| Collection    |   Documents | Expected   |
|---------------|-------------|------------|
| activity      |           0 |            |
| auth_roles    |           0 |            |
| auth_subjects |           0 |            |
| devicestatus  |         733 | ✓          |
| entries       |        2241 | ✓          |
| food          |           0 |            |
| profile       |           1 | ✓          |
| settings      |           0 |            |
| treatments    |        1635 | ✓          |

## 2. Entries (CGM readings)

**Total documents:** 2,241

**Date range** (`date`): `1790862531545.0` → `1791535614247.0`

### Fields and Types

| Field      | Types (count)   |
|------------|-----------------|
| _id        | ObjectId(50)    |
| created_at | string(50)      |
| date       | number(50)      |
| dateString | string(50)      |
| device     | string(50)      |
| direction  | string(50)      |
| isValid    | number(50)      |
| sgv        | number(50)      |
| type       | string(50)      |

### SGV Value Distribution

```json
{
  "total_sgv": 2241,
  "min": 56,
  "max": 321,
  "mean": 141.8,
  "below_20_count": 0,
  "above_500_count": 0
}
```

### Data Gaps (CGM)

```json
{
  "total_readings_sampled": 2241,
  "period_hours": 187.0,
  "median_interval_min": 5.0,
  "mean_interval_min": 5.01,
  "max_gap_min": 12.0,
  "gaps_over_15min": 0,
  "gaps_over_30min": 0,
  "gaps_over_60min": 0,
  "pct_expected_5min": 99.6
}
```

### Duplicates

Duplicate (date, sgv) groups: **0**

### Direction Values

| Direction     |   Count |
|---------------|---------|
| Flat          |    1571 |
| FortyFiveUp   |     244 |
| FortyFiveDown |     227 |
| SingleUp      |      99 |
| SingleDown    |      77 |
| DoubleDown    |      13 |
| DoubleUp      |      10 |

## 3. Treatments

**Total documents:** 1,635

**Date range** (`created_at`): `2026-09-28T07:00:23.000Z` → `2026-10-09T08:37:18.000Z`

### Event Types

| eventType        |   Count |
|------------------|---------|
| Temp Basal       |     966 |
| Correction Bolus |     324 |
| Temporary Target |      81 |
| Note             |      78 |
| Profile Switch   |      71 |
| Meal Bolus       |      65 |
| Bolus Wizard     |      25 |
| Carb Correction  |      10 |
| OpenAPS Offline  |       4 |
| BG Check         |       3 |
| Insulin Change   |       2 |
| Site Change      |       2 |
| Sensor Change    |       2 |
| Announcement     |       1 |
| Settings Export  |       1 |

### Fields and Types

| Field                  | Types (count)   |
|------------------------|-----------------|
| _id                    | ObjectId(50)    |
| absolute               | number(29)      |
| created_at             | string(50)      |
| date                   | number(13)      |
| duration               | number(33)      |
| durationInMilliseconds | number(31)      |
| endId                  | number(28)      |
| enteredBy              | string(37)      |
| eventType              | string(50)      |
| insulin                | number(13)      |
| isSMB                  | number(13)      |
| isValid                | number(50)      |
| notes                  | string(4)       |
| originalCustomizedName | string(4)       |
| originalDuration       | number(6)       |
| originalEnd            | number(4)       |
| originalPercentage     | number(4)       |
| originalProfileName    | string(6)       |
| originalTimeshift      | number(4)       |
| percentage             | number(2)       |
| profile                | string(2)       |
| profileJson            | string(6)       |
| pumpId                 | number(42)      |
| pumpSerial             | string(42)      |
| pumpType               | string(42)      |
| rate                   | number(29)      |
| reason                 | string(2)       |
| targetBottom           | number(2)       |
| targetTop              | number(2)       |
| timeshift              | number(2)       |
| timestamp              | number(2)       |
| type                   | string(42)      |
| units                  | string(2)       |

### Duplicates

Duplicate (created_at, eventType) groups: **0**

## 4. Device Status

**Total documents:** 733

**Date range** (`created_at`): `2026-10-07T14:56:58.149Z` → `2026-10-09T08:47:11.896Z`

### Structure Analysis

```json
{
  "sample_size": 20,
  "has_openaps": "20/20",
  "has_pump": "20/20",
  "has_uploader": "20/20",
  "has_loop": "0/20",
  "has_configuration": "20/20",
  "openaps_top_keys": [
    "enacted",
    "iob",
    "suggested"
  ],
  "openaps_suggested_keys": [
    "COB",
    "IOB",
    "algorithm",
    "bg",
    "carbsReq",
    "carbsReqWithin",
    "consoleError",
    "consoleLog",
    "deliverAt",
    "duration",
    "eventualBG",
    "insulinReq",
    "isfMgdlForCarbs",
    "predBGs",
    "rate",
    "reason",
    "runningDynamicIsf",
    "sensitivityRatio",
    "targetBG",
    "tick",
    "timestamp",
    "units",
    "variable_sens"
  ],
  "openaps_enacted_keys": [
    "COB",
    "IOB",
    "algorithm",
    "bg",
    "carbsReq",
    "carbsReqWithin",
    "consoleError",
    "consoleLog",
    "deliverAt",
    "duration",
    "eventualBG",
    "insulinReq",
    "predBGs",
    "rate",
    "reason",
    "received",
    "requested",
    "runningDynamicIsf",
    "sensitivityRatio",
    "smb",
    "targetBG",
    "tick",
    "timestamp",
    "units",
    "variable_sens"
  ],
  "openaps_iob_keys": [
    "activity",
    "basaliob",
    "iob",
    "time"
  ],
  "predBG_types": [
    "IOB",
    "UAM",
    "ZT"
  ],
  "pump_keys": [
    "battery",
    "clock",
    "extended",
    "reservoir",
    "status"
  ]
}
```

### Fields and Types (top 3 levels)

| Field                                                                | Types (count)   |
|----------------------------------------------------------------------|-----------------|
| _id                                                                  | ObjectId(30)    |
| configuration                                                        | object(30)      |
| configuration.aps                                                    | string(3)       |
| configuration.apsConfiguration                                       | object(3)       |
| configuration.apsConfiguration.DynISFAdjust                          | number(3)       |
| configuration.apsConfiguration.use_dynamic_sensitivity               | number(3)       |
| configuration.insulin                                                | number(3)       |
| configuration.insulinConfiguration                                   | object(3)       |
| configuration.overviewConfiguration                                  | object(3)       |
| configuration.overviewConfiguration.QuickWizard                      | string(3)       |
| configuration.overviewConfiguration.activity_duration                | number(3)       |
| configuration.overviewConfiguration.activity_target                  | number(3)       |
| configuration.overviewConfiguration.boluswizard_percentage           | number(3)       |
| configuration.overviewConfiguration.eatingsoon_duration              | number(3)       |
| configuration.overviewConfiguration.eatingsoon_target                | number(3)       |
| configuration.overviewConfiguration.high_mark                        | number(3)       |
| configuration.overviewConfiguration.hypo_duration                    | number(3)       |
| configuration.overviewConfiguration.hypo_target                      | number(3)       |
| configuration.overviewConfiguration.low_mark                         | number(3)       |
| configuration.overviewConfiguration.statuslights_bage_critical       | number(3)       |
| configuration.overviewConfiguration.statuslights_bage_warning        | number(3)       |
| configuration.overviewConfiguration.statuslights_bat_critical        | number(3)       |
| configuration.overviewConfiguration.statuslights_bat_warning         | number(3)       |
| configuration.overviewConfiguration.statuslights_cage_critical       | number(3)       |
| configuration.overviewConfiguration.statuslights_cage_warning        | number(3)       |
| configuration.overviewConfiguration.statuslights_iage_critical       | number(3)       |
| configuration.overviewConfiguration.statuslights_iage_warning        | number(3)       |
| configuration.overviewConfiguration.statuslights_res_critical        | number(3)       |
| configuration.overviewConfiguration.statuslights_res_warning         | number(3)       |
| configuration.overviewConfiguration.statuslights_sage_critical       | number(3)       |
| configuration.overviewConfiguration.statuslights_sage_warning        | number(3)       |
| configuration.overviewConfiguration.statuslights_sbat_critical       | number(3)       |
| configuration.overviewConfiguration.statuslights_sbat_warning        | number(3)       |
| configuration.overviewConfiguration.units                            | string(3)       |
| configuration.overviewConfiguration.used_autosens_on_main_phone      | number(3)       |
| configuration.pump                                                   | string(3)       |
| configuration.safetyConfiguration                                    | object(3)       |
| configuration.safetyConfiguration.age                                | string(3)       |
| configuration.safetyConfiguration.treatmentssafety_maxbolus          | number(3)       |
| configuration.safetyConfiguration.treatmentssafety_maxcarbs          | number(3)       |
| configuration.sensitivity                                            | number(3)       |
| configuration.sensitivityConfiguration                               | object(3)       |
| configuration.sensitivityConfiguration.absorption_cutoff             | number(3)       |
| configuration.sensitivityConfiguration.autosens_max                  | number(3)       |
| configuration.sensitivityConfiguration.autosens_min                  | number(3)       |
| configuration.sensitivityConfiguration.openaps_smb_min_5m_carbimpact | number(3)       |
| configuration.smoothing                                              | string(3)       |
| configuration.version                                                | string(3)       |
| created_at                                                           | string(30)      |
| device                                                               | string(30)      |
| isCharging                                                           | number(30)      |
| openaps                                                              | object(30)      |
| openaps.enacted                                                      | object(10)      |
| openaps.enacted.COB                                                  | number(10)      |
| openaps.enacted.IOB                                                  | number(10)      |
| openaps.enacted.algorithm                                            | string(10)      |
| openaps.enacted.bg                                                   | number(10)      |
| openaps.enacted.carbsReq                                             | number(1)       |
| openaps.enacted.carbsReqWithin                                       | number(1)       |
| openaps.enacted.consoleError                                         | array(10)       |
| openaps.enacted.consoleLog                                           | array(10)       |
| openaps.enacted.deliverAt                                            | string(10)      |
| openaps.enacted.duration                                             | number(10)      |
| openaps.enacted.eventualBG                                           | number(10)      |
| openaps.enacted.insulinReq                                           | number(10)      |
| openaps.enacted.predBGs                                              | object(10)      |
| openaps.enacted.rate                                                 | number(10)      |
| openaps.enacted.reason                                               | string(10)      |
| openaps.enacted.received                                             | number(10)      |
| openaps.enacted.requested                                            | object(10)      |
| openaps.enacted.runningDynamicIsf                                    | number(10)      |
| openaps.enacted.sensitivityRatio                                     | number(10)      |
| openaps.enacted.smb                                                  | number(10)      |
| openaps.enacted.targetBG                                             | number(10)      |
| openaps.enacted.tick                                                 | string(10)      |
| openaps.enacted.timestamp                                            | string(10)      |
| openaps.enacted.units                                                | number(2)       |
| openaps.enacted.variable_sens                                        | number(10)      |
| openaps.iob                                                          | object(30)      |
| openaps.iob.activity                                                 | number(30)      |
| openaps.iob.basaliob                                                 | number(30)      |
| openaps.iob.iob                                                      | number(30)      |
| openaps.iob.time                                                     | string(30)      |
| openaps.suggested                                                    | object(30)      |
| openaps.suggested.COB                                                | number(30)      |
| openaps.suggested.IOB                                                | number(30)      |
| openaps.suggested.algorithm                                          | string(30)      |
| openaps.suggested.bg                                                 | number(30)      |
| openaps.suggested.carbsReq                                           | number(5)       |
| openaps.suggested.carbsReqWithin                                     | number(5)       |
| openaps.suggested.consoleError                                       | array(30)       |
| openaps.suggested.consoleLog                                         | array(30)       |
| openaps.suggested.deliverAt                                          | string(30)      |
| openaps.suggested.duration                                           | number(21)      |
| openaps.suggested.eventualBG                                         | number(30)      |
| openaps.suggested.insulinReq                                         | number(30)      |
| openaps.suggested.isfMgdlForCarbs                                    | number(30)      |
| openaps.suggested.predBGs                                            | object(30)      |
| openaps.suggested.rate                                               | number(21)      |
| openaps.suggested.reason                                             | string(30)      |
| openaps.suggested.runningDynamicIsf                                  | number(30)      |
| openaps.suggested.sensitivityRatio                                   | number(30)      |
| openaps.suggested.targetBG                                           | number(30)      |
| openaps.suggested.tick                                               | string(30)      |
| openaps.suggested.timestamp                                          | string(30)      |
| openaps.suggested.units                                              | number(8)       |
| openaps.suggested.variable_sens                                      | number(30)      |
| pump                                                                 | object(30)      |
| pump.battery                                                         | object(30)      |
| pump.clock                                                           | string(30)      |
| pump.extended                                                        | object(30)      |
| pump.extended.ActiveProfile                                          | string(30)      |
| pump.extended.BaseBasalRate                                          | number(30)      |
| pump.extended.LastBolus                                              | string(30)      |
| pump.extended.LastBolusAmount                                        | number(30)      |
| pump.extended.TempBasalAbsoluteRate                                  | number(16)      |
| pump.extended.TempBasalRemaining                                     | number(29)      |
| pump.extended.TempBasalStart                                         | string(29)      |
| pump.extended.Version                                                | string(30)      |
| pump.reservoir                                                       | number(30)      |
| pump.status                                                          | object(30)      |
| pump.status.status                                                   | string(30)      |
| pump.status.timestamp                                                | string(30)      |
| uploaderBattery                                                      | number(30)      |

### Devices

| Device                   |   Count |
|--------------------------|---------|
| openaps://Google Pixel 8 |     733 |

## 5. Profile

**Total documents:** 1

### Profile Structure

```json
{
  "count": 1,
  "profile_names": [
    "normal"
  ],
  "profile_fields": [
    "basal",
    "carbratio",
    "carbs_hr",
    "delay",
    "dia",
    "sens",
    "target_high",
    "target_low",
    "timezone",
    "units"
  ],
  "basal_segments": 1,
  "carbratio_segments": 1,
  "sens_segments": 1,
  "target_low_segments": 1,
  "target_high_segments": 1,
  "dia": 7,
  "units": "mg/dl",
  "timezone": "UTC",
  "defaultProfile": "normal",
  "startDate": "1970-01-01T00:00:00.000Z"
}
```

## 6. Summary & Data Quality Assessment

### Key Findings

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

## 7. Nightscout Schema Reference

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
