#!/usr/bin/env python3
"""
Generate small SD + multi-STAT + responders Parquet fixtures for Databricks proto ingestion.

Grain:
  pit_key = f"{customer_id}||{campaign_id}"  (same key used across SD and all STAT files)

Outputs (under databricks/proto/fixtures/ by default):
  Accident & Illness supplemental LOB; product_line = sub-product code (see FIXTURE_README).
  stat_promotion.parquet      — STAT: promotion-history style attributes
  stat_membership.parquet     — STAT: membership style attributes
  stat_demographics.parquet   — STAT: demographic snapshot attributes
  responders.parquet          — positive responders subset (append source mimic)

Usage:
  py -3 scripts/generate_sd_stat_fixtures.py --out databricks/proto/fixtures --n 8000
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import polars as pl


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--out", type=Path, default=Path("databricks/proto/fixtures"))
    p.add_argument("--n", type=int, default=8_000, help="Row count per core table")
    p.add_argument("--seed", type=int, default=42)
    args = p.parse_args()

    out: Path = args.out
    out.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(args.seed)
    n = args.n

    customer_ids = np.array([f"CUST-{i + 1:08d}" for i in range(n)], dtype=object)
    campaign_pool = np.array([f"CAMP-JUN-2026-{k:04d}" for k in range(120)], dtype=object)
    campaign_ids = rng.choice(campaign_pool, size=n, replace=True)
    pit_keys = np.array([f"{c}||{p}" for c, p in zip(customer_ids, campaign_ids)], dtype=object)

    # Accident & Illness supplemental LOB — child-model slice per sub-product (stable codes for train/score).
    product_codes = np.array(
        [
            "HOSPITAL_ACCIDENT",  # (a) daily hospital cash; accident hospitalization
            "RECUPERATIVE_CARE",  # (b) recovery from illness or accident; pre-ex; no wait
            "ACCIDENT_EXPENSE",  # (c) lump-sum: burns, fractures, sports injuries, etc.
            "CRITICAL_ILLNESS",  # (d) lump-sum: cancer, stroke, MI, paralysis, coma
        ],
        dtype=object,
    )
    offer_labels = np.array(
        [
            "Hospital Accident Insurance",
            "Recuperative Care Plan",
            "Accident Expense Coverage",
            "Critical Illness & Injury Insurance",
        ],
        dtype=object,
    )
    line_idx = rng.choice(np.arange(4, dtype=np.int64), size=n, p=[0.28, 0.27, 0.25, 0.20])
    product_line = product_codes[line_idx]
    offer_type = offer_labels[line_idx]

    # --- SD (score driver): one row per (customer, campaign) touch ---
    response_yes = rng.random(n) < 0.035
    sd = pl.DataFrame(
        {
            "pit_key": pit_keys,
            "customer_id": customer_ids,
            "campaign_id": campaign_ids,
            "product_line": product_line,
            "campaign_channel": rng.choice(
                np.array(["Email", "SMS", "Direct Mail", "Postcard"]), size=n
            ),
            "offer_type": offer_type,
            "state": rng.choice(
                np.array(["CA", "OR", "WA", "AZ", "NV", "TX", "FL", "NY"]), size=n
            ),
            "response_flag": response_yes.astype(np.int8),
            "income": rng.lognormal(mean=11.0, sigma=0.5, size=n).astype(np.float64),
            "monthly_premium": rng.gamma(shape=2.5, scale=40.0, size=n).astype(np.float64),
            "months_since_last_claim": rng.integers(0, 48, size=n, endpoint=True).astype(np.float64),
            "clv": rng.lognormal(mean=8.6, sigma=0.4, size=n).astype(np.float64),
        }
    )
    sd.write_parquet(out / "sd_driver.parquet", compression="zstd")

    # --- STAT: promotion (1:1 on pit_key, introduce small null noise) ---
    promo = pl.DataFrame(
        {
            "pit_key": pit_keys,
            "promo_touch_count_90d": rng.integers(0, 8, size=n, endpoint=True),
            "last_promo_channel": rng.choice(
                np.array(["Email", "SMS", "Direct Mail", None]), size=n, p=[0.35, 0.3, 0.25, 0.1]
            ),
            "promo_spend_band": rng.choice(np.array(["A", "B", "C", "D"]), size=n),
        }
    )
    promo.write_parquet(out / "stat_promotion.parquet", compression="zstd")

    # --- STAT: membership ---
    member = pl.DataFrame(
        {
            "pit_key": pit_keys,
            "member_tier": rng.choice(np.array(["BASIC", "PLUS", "PREMIUM"]), size=n),
            "tenure_months": rng.integers(1, 240, size=n, endpoint=True),
            "active_products_ct": rng.integers(1, 6, size=n, endpoint=True),
        }
    )
    member.write_parquet(out / "stat_membership.parquet", compression="zstd")

    # --- STAT: demographics (subset of keys missing to simulate late-arriving STAT) ---
    keep = rng.random(n) > 0.03
    demo_keys = pit_keys[keep]
    demo = pl.DataFrame(
        {
            "pit_key": demo_keys,
            "demo_region_bucket": rng.choice(np.array(["NE", "SE", "MW", "W", "SW"]), size=demo_keys.size),
            "income_band": rng.choice(np.array(["<40k", "40-75k", "75-120k", "120k+"]), size=demo_keys.size),
        }
    )
    demo.write_parquet(out / "stat_demographics.parquet", compression="zstd")

    # --- Responders: only positives (subset of SD keys where response_flag=1) ---
    pos_idx = np.where(response_yes)[0]
    r_pit = pit_keys[pos_idx]
    responders = pl.DataFrame(
        {
            "pit_key": r_pit,
            "customer_id": customer_ids[pos_idx],
            "campaign_id": campaign_ids[pos_idx],
            "product_line": product_line[pos_idx],
            "responded_at": rng.integers(20260101, 20260630, size=len(pos_idx)),
            "response_channel": rng.choice(np.array(["Email", "Web", "Call"]), size=len(pos_idx)),
        }
    )
    responders.write_parquet(out / "responders.parquet", compression="zstd")

    meta = out / "FIXTURE_README.txt"
    meta.write_text(
        "Generated SD/STAT/responders prototype fixtures.\n"
        f"rows_sd={n} rows_demo={len(demo)} rows_responders={len(responders)}\n"
        "Join key: pit_key = customer_id || campaign_id (string).\n"
        "LOB: Accident & Illness supplemental. product_line codes (train/score one per job):\n"
        "  HOSPITAL_ACCIDENT | RECUPERATIVE_CARE | ACCIDENT_EXPENSE | CRITICAL_ILLNESS\n",
        encoding="utf-8",
    )
    print(f"Wrote fixtures to {out.resolve()}")


if __name__ == "__main__":
    main()
