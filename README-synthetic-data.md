# Synthetic insurance + marketing dataset (2M rows)

This folder is produced by [`scripts/generate_synthetic_2m.py`](scripts/generate_synthetic_2m.py). Data is **entirely synthetic** (no real customers); it is meant to exercise ingestion, cleaning, preprocessing, and modeling workflows.

## Output layout

- Default directory: `synthetic_insurance_marketing_2m/`
- Files: `part-0000.parquet` … `part-0009.parquet` (when `--n 2000000` and `--chunk-rows 200000`)
- Sidecar: `generation_meta.txt` (seed, chunk size, row counts)

## Dependencies

```bash
py -3 -m pip install -r requirements-synth.txt
```

## Regenerate

```bash
py -3 scripts/generate_synthetic_2m.py --out synthetic_insurance_marketing_2m --n 2000000 --chunk-rows 200000 --seed 42
```

CLI flags:

| Flag | Meaning |
|------|--------|
| `--out` | Output directory |
| `--n` | Total rows across all parts (includes exact duplicate rows injected per chunk) |
| `--chunk-rows` | Target rows per Parquet file (primary + duplicate rows) |
| `--seed` | Base RNG seed (reproducible) |
| `--n-templates` | Marketing template catalog size (default 10_000) |
| `--exact-dup-rate` | Duplicate row fraction per chunk (default `0.005`) |

## Schema (48 columns)

**Insurance-aligned (34):** `customer_id`, `campaign_id`, `campaign_month`, `campaign_channel`, `channel_preference`, `last_campaign_response`, `days_since_last_campaign`, `number_of_previous_campaigns`, `offer_type`, `region_cluster`, `Customer`, `State`, `Response`, `Coverage`, `Education`, `EmploymentStatus`, `Gender`, `Location Code`, `Marital Status`, `Policy Type`, `Policy`, `Renew Offer Type`, `Sales Channel`, `Vehicle Class`, `Vehicle Size`, `Customer Lifetime Value`, `Income`, `Monthly Premium Auto`, `Months Since Last Claim`, `Months Since Policy Inception`, `Number of Open Complaints`, `Number of Policies`, `Total Claim Amount`, `Effective To Date`

**Marketing-style (12):** `marketing_company`, `marketing_campaign_type`, `marketing_channel_used`, `marketing_clicks`, `marketing_impressions`, `marketing_eng_score`, `marketing_market_segment`, `marketing_conversion_rate_str`, `marketing_roi_str`, `marketing_acquisition_cost`, `marketing_target_audience`, `marketing_language`

**Extra:** `campaign_cohort_key` (maps row to marketing template bucket), `Age` (numeric with outliers / nulls), `Income_raw` (optional comma-formatted string mirror of `Income`)

## Known imperfections (by design)

- **Nulls:** MCAR on several string columns; MAR on `Income` when `EmploymentStatus` is `Unemployed`
- **Sentinel strings:** literal `na` / `N/A` style tokens in some categorical fields
- **Duplicate keys:** `customer_id` repeats after the first 1.9M primary-row indices; exact duplicate rows appended per chunk
- **Inconsistent enums:** mixed `Gender` / `campaign_month` spellings
- **Mixed date strings:** `Effective To Date` uses several string formats
- **Outliers:** `Age` (including impossible values), negative months fields, very large premiums
- **Typos:** occasional bad `State` / `Vehicle Class` tokens
- **Label noise:** small random flips on `Response` after logistic generation

`Response` is generated from a **noisy logistic** model of latent features (income, complaints, marketing engagement, channel match) so models have learnable signal underneath the mess.

## Loading examples

**Polars (lazy, all parts):**

```python
import polars as pl

lf = pl.scan_parquet("synthetic_insurance_marketing_2m/*.parquet")
print(lf.select(pl.len()).collect())
```

**Pandas:**

```python
import pandas as pd

df = pd.read_parquet("synthetic_insurance_marketing_2m", engine="pyarrow")
```

## Modeling note

Use **group-aware splits** on `customer_id` (or aggregate to one row per customer) before training response models, otherwise train/test leakage is likely.

## Verify row count

```bash
py -3 -c "import polars as pl; lf=pl.scan_parquet('synthetic_insurance_marketing_2m/*.parquet'); print(lf.select(pl.len()).collect().item())"
```

## Disk

Rough order of magnitude: hundreds of MB to a few GB depending on compression and string cardinality; `zstd` is enabled on write.
