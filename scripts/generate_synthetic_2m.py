#!/usr/bin/env python3
"""
Generate a reproducible 2M-row synthetic insurance+marketing dataset with
intentional data-quality defects. Writes chunked Parquet files.

Usage:
  py -3 scripts/generate_synthetic_2m.py --out synthetic_insurance_marketing_2m --n 2000000
"""

from __future__ import annotations

import argparse
import hashlib
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

import numpy as np
import polars as pl

logger = logging.getLogger(__name__)

UNIQUE_CUSTOMERS = 1_900_000
TOTAL_ROWS_DEFAULT = 2_000_000


@dataclass(frozen=True)
class DefectRates:
    mcar_null_rate: float = 0.06
    mar_income_unemployed_boost: float = 0.35
    sentinel_rate: float = 0.04
    gender_noise_rate: float = 0.12
    campaign_month_mess_rate: float = 0.25
    date_format_entropy: float = 1.0  # use 4 formats
    outlier_age_rate: float = 0.08
    typo_state_rate: float = 0.003
    garbage_vehicle_rate: float = 0.002
    negative_months_rate: float = 0.005
    absurd_premium_rate: float = 0.003
    logical_contradiction_rate: float = 0.002
    exact_dup_row_rate: float = 0.005
    income_raw_fill_rate: float = 0.05
    response_label_noise: float = 0.015


def _sigmoid(x: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-np.clip(x, -30.0, 30.0)))


def _customer_id_from_num(nums: np.ndarray) -> list[str]:
    return [f"CUST-{int(n):08d}" for n in nums]


def _campaign_id(rng: np.random.Generator, n: int) -> list[str]:
    months = rng.integers(1000, 9999, size=n)
    tail = rng.integers(1000, 9999, size=n)
    return [f"CAMP-JUN-2026-{m}-{t}" for m, t in zip(months.tolist(), tail.tolist())]


def build_marketing_templates(rng: np.random.Generator, n_templates: int = 10_000) -> dict[str, np.ndarray]:
    companies = np.array(
        ["Innovate Industries", "NexGen Systems", "Alpha Innovations", "DataTech Solutions", "TechCorp"]
    )
    camp_types = np.array(["Email", "Display", "Search", "Social Media", "Influencer"])
    ch_used = np.array(["Google Ads", "YouTube", "Instagram", "Facebook", "Email", "Website"])
    segments = np.array(
        ["Health & Wellness", "Fashionistas", "Outdoor Adventurers", "Tech Enthusiasts", "Foodies"]
    )
    audiences = np.array(["Men 18-24", "Women 35-44", "Men 25-34", "Women 25-34", "All Ages"])
    langs = np.array(["English", "Spanish", "German", "French", "Mandarin"])

    return {
        "marketing_company": rng.choice(companies, size=n_templates),
        "marketing_campaign_type": rng.choice(camp_types, size=n_templates),
        "marketing_channel_used": rng.choice(ch_used, size=n_templates),
        "marketing_clicks": rng.integers(50, 1200, size=n_templates),
        "marketing_impressions": rng.integers(1000, 10000, size=n_templates),
        "marketing_eng_score": rng.integers(1, 11, size=n_templates),
        "marketing_market_segment": rng.choice(segments, size=n_templates),
        "marketing_conversion_rate_str": rng.choice(["0.0%", "0.1%", "0.2%"], size=n_templates),
        "marketing_roi_str": np.array(
            [f"{x:.1f}%" for x in rng.uniform(2.0, 9.0, size=n_templates)], dtype=object
        ),
        "marketing_acquisition_cost": rng.integers(5000, 20000, size=n_templates),
        "marketing_target_audience": rng.choice(audiences, size=n_templates),
        "marketing_language": rng.choice(langs, size=n_templates),
    }


def cohort_key_to_template_idx(
    campaign_ids: list[str], region_clusters: np.ndarray, offer_types: np.ndarray, n_templates: int
) -> np.ndarray:
    """Deterministic-ish mapping from row features to template bucket."""
    n = len(campaign_ids)
    h = np.empty(n, dtype=np.uint64)
    for i in range(n):
        raw = f"{campaign_ids[i]}|{region_clusters[i]}|{offer_types[i]}".encode()
        h[i] = int.from_bytes(hashlib.md5(raw).digest()[:8], "little", signed=False)
    return (h % np.uint64(n_templates)).astype(np.int64)


def sample_insurance_categoricals(rng: np.random.Generator, n: int) -> dict[str, np.ndarray]:
    channels = np.array(["Email", "SMS", "Direct Mail", "Postcard", "Call Center"])
    pref = np.array(["Email", "SMS", "Direct Mail", "Postcard", "Call Center", "Web", "Agent"])
    last_resp = np.array(["", "Opened", "Clicked", "bounced", "No Response", "Ignored"])
    offers = np.array(["Vehicle Insurance", "Life Insurance", "Cross Sell", "Home Insurance", "Upsell", "Health Insurance"])
    states = np.array(
        [
            "California",
            "Oregon",
            "Washington",
            "Arizona",
            "Nevada",
            "Texas",
            "Florida",
            "New York",
            "Illinois",
            "Ohio",
        ]
    )
    coverage = np.array(["Basic", "Extended", "Premium"])
    education = np.array(["Bachelor", "College", "High School or Below", "Master", "Doctor", ""])
    employment = np.array(["Employed", "Unemployed", "Medical Leave", "Disabled", "Retired"])
    loc = np.array(["Urban", "Suburban", "Rural"])
    marital = np.array(["Married", "Single", "Divorced", "Widowed", ""])
    policy_type = np.array(["Personal Auto", "Corporate Auto", "Special Auto"])
    policy = np.array(["Personal L1", "Personal L2", "Personal L3", "Corporate L1", "Corporate L2", "Corporate L3", "Special L1", "Special L2", "Special L3"])
    renew = np.array(["Offer1", "Offer2", "Offer3", "Offer4"])
    sales = np.array(["Agent", "Web", "Call Center", "Branch"])
    vclass = np.array(["Four-Door Car", "Two-Door Car", "SUV", "Luxury SUV", "Luxury Car", "Sports Car", ""])
    vsize = np.array(["Small", "Medsize", "Large", ""])

    region_idx = rng.integers(1, 32, size=n)
    region_cluster = np.array([f"RC-{i:02d}" for i in region_idx])

    u1 = rng.integers(65, 91, size=n, dtype=np.int32)
    u2 = rng.integers(65, 91, size=n, dtype=np.int32)
    nums = rng.integers(10000, 99999, size=n, dtype=np.int32)
    cust_tokens = np.fromiter(
        (f"{chr(int(a))}{chr(int(b))}{int(num)}" for a, b, num in zip(u1, u2, nums)),
        count=n,
        dtype=object,
    )

    return {
        "campaign_channel": rng.choice(channels, size=n),
        "channel_preference": rng.choice(pref, size=n),
        "last_campaign_response": rng.choice(last_resp, size=n),
        "offer_type": rng.choice(offers, size=n),
        "region_cluster": region_cluster,
        "Customer": cust_tokens,
        "State": rng.choice(states, size=n),
        "Coverage": rng.choice(coverage, size=n),
        "Education": rng.choice(education, size=n),
        "EmploymentStatus": rng.choice(employment, size=n),
        "Gender": rng.choice(
            np.array(["M", "F", "Male", "Female", "male", "female", "MALE", "FEMALE", "m", "f"]),
            size=n,
            p=np.array([0.22, 0.22, 0.12, 0.12, 0.1, 0.1, 0.04, 0.04, 0.02, 0.02]),
        ),
        "Location Code": rng.choice(loc, size=n),
        "Marital Status": rng.choice(marital, size=n),
        "Policy Type": rng.choice(policy_type, size=n),
        "Policy": rng.choice(policy, size=n),
        "Renew Offer Type": rng.choice(renew, size=n),
        "Sales Channel": rng.choice(sales, size=n),
        "Vehicle Class": rng.choice(vclass, size=n),
        "Vehicle Size": rng.choice(vsize, size=n),
    }


def format_effective_date_strings(rng: np.random.Generator, dates_ord: np.ndarray) -> np.ndarray:
    """Mix 4 string date formats (ordinal days since epoch internal)."""
    out = np.empty(len(dates_ord), dtype=object)
    for i, ord_day in enumerate(dates_ord.tolist()):
        # base date from ordinal
        from datetime import date, timedelta

        d0 = date(2008, 1, 1) + timedelta(days=int(ord_day) % 5500)
        fmt = rng.integers(0, 4)
        if fmt == 0:
            out[i] = d0.strftime("%m/%d/%Y")
        elif fmt == 1:
            out[i] = d0.strftime("%Y-%m-%d")
        elif fmt == 2:
            out[i] = d0.strftime("%d-%b-%Y")
        else:
            out[i] = d0.strftime("%d/%m/%Y")
    return out


def mess_campaign_month(rng: np.random.Generator, months: np.ndarray, mess_rate: float) -> np.ndarray:
    variants = np.array(["June", "jun", "Jun", "06/2026", "6-2026", "June 2026", "May-2026", "July 2026"])
    out = months.copy()
    mask = rng.random(len(months)) < mess_rate
    out[mask] = rng.choice(variants, size=int(mask.sum()))
    return out


def inject_sentinels(rng: np.random.Generator, arr: np.ndarray, rate: float, sentinel: str = "na") -> np.ndarray:
    out = arr.astype(object)
    m = rng.random(len(out)) < rate
    out[m] = sentinel
    return out


def maybe_null_strings(rng: np.random.Generator, arr: np.ndarray, rate: float) -> np.ndarray:
    out = arr.astype(object)
    m = rng.random(len(out)) < rate
    out[m] = None
    return out


def generate_chunk(
    global_start: int,
    size: int,
    dup_n: int,
    seed: int,
    templates: dict[str, np.ndarray],
    n_templates: int,
    rates: DefectRates,
) -> pl.DataFrame:
    # Stable per-chunk RNG stream (primary row count drives customer assignment progression).
    rng = np.random.default_rng((seed + global_start * 1_000_003) % (2**63 - 1))

    global_idx = np.arange(global_start, global_start + size, dtype=np.int64)
    cust_num = np.where(
        global_idx < UNIQUE_CUSTOMERS,
        global_idx + 1,
        rng.integers(1, UNIQUE_CUSTOMERS + 1, size=size),
    ).astype(np.int64)

    customer_id = _customer_id_from_num(cust_num)
    campaign_id = _campaign_id(rng, size)

    cats = sample_insurance_categoricals(rng, size)

    days_since = rng.uniform(0, 365, size=size)
    n_prev = rng.integers(0, 18, size=size)

    clv = rng.lognormal(mean=8.5, sigma=0.45, size=size)
    income = rng.lognormal(mean=10.5, sigma=0.55, size=size)
    premium = rng.gamma(shape=3.0, scale=35.0, size=size)
    months_claim = rng.uniform(0, 40, size=size)
    months_incept = rng.uniform(0, 120, size=size)
    complaints = rng.integers(0, 4, size=size)
    n_policies = rng.integers(1, 10, size=size)
    claim_amt = rng.exponential(scale=250.0, size=size)

    # MAR: higher missing income for unemployed
    emp = cats["EmploymentStatus"]
    income_null = (rng.random(size) < rates.mcar_null_rate * 0.5) | (
        (emp == "Unemployed") & (rng.random(size) < rates.mar_income_unemployed_boost)
    )
    income_f = income.astype(np.float64)
    income_f[income_null] = np.nan

    # Template lookup
    tmpl_idx = cohort_key_to_template_idx(campaign_id, cats["region_cluster"], cats["offer_type"], n_templates)
    m_eng = templates["marketing_eng_score"][tmpl_idx].astype(np.float64)
    m_clicks = templates["marketing_clicks"][tmpl_idx].astype(np.float64)

    # Latent logistic for Response (clean signal before label noise)
    med_inc = float(np.nanmedian(income_f)) if np.any(~np.isnan(income_f)) else 36_000.0
    inc_z = (np.log1p(np.nan_to_num(income_f, nan=med_inc)) - 10.5) / 0.6
    comp_z = (complaints.astype(np.float64) - 0.5) / 1.2
    eng_z = (m_eng - 5.5) / 3.0
    match = (cats["campaign_channel"] == cats["channel_preference"]).astype(np.float64)
    latent = -0.35 + 0.45 * inc_z - 0.35 * comp_z + 0.28 * eng_z + 0.22 * match + rng.normal(0.0, 0.75, size=size)
    p = _sigmoid(latent)
    response_yes = rng.random(size) < p
    response = np.where(response_yes, "Yes", "No")

    # Label noise
    flip = rng.random(size) < rates.response_label_noise
    response[flip] = np.where(response[flip] == "Yes", "No", "Yes")

    # Age: mostly 18-85, outliers
    age = rng.normal(48.0, 16.0, size=size)
    out_mask = rng.random(size) < rates.outlier_age_rate
    age[out_mask] = rng.choice([999.0, 200.0, -3.0, 120.0, 0.0], size=int(out_mask.sum()))
    age_null = rng.random(size) < 0.02
    age[age_null] = np.nan

    # Logical contradictions
    bad = rng.random(size) < rates.logical_contradiction_rate
    months_incept = months_incept.copy()
    months_incept[bad] = rng.uniform(-30, -1, size=int(bad.sum()))

    # Negative months since claim
    badc = rng.random(size) < rates.negative_months_rate
    months_claim = months_claim.copy()
    months_claim[badc] = rng.uniform(-12, -0.5, size=int(badc.sum()))

    # Absurd premium
    badp = rng.random(size) < rates.absurd_premium_rate
    premium = premium.copy()
    premium[badp] = rng.uniform(50_000, 500_000, size=int(badp.sum()))

    ord_days = rng.integers(0, 5500, size=size)
    eff_dates = format_effective_date_strings(rng, ord_days)

    campaign_month_base = np.full(size, "June", dtype=object)
    campaign_month = mess_campaign_month(rng, campaign_month_base, rates.campaign_month_mess_rate)

    # Typos in State
    states = cats["State"].astype(object)
    typo_m = rng.random(size) < rates.typo_state_rate
    states = states.copy()
    states[typo_m] = np.where(states[typo_m] == "Oregon", "Oregeon", states[typo_m])

    # Garbage vehicle
    vcls = cats["Vehicle Class"].astype(object)
    gv = rng.random(size) < rates.garbage_vehicle_rate
    vcls = vcls.copy()
    vcls[gv] = "???CLASS"

    # Gender extra noise
    gender = cats["Gender"].astype(object)
    gn = rng.random(size) < rates.gender_noise_rate
    gender = gender.copy()
    gender[gn] = rng.choice(["M", "f", "FEMALE", "Male", "na"], size=int(gn.sum()))

    # Sentinel strings on various cols
    last_resp = inject_sentinels(rng, cats["last_campaign_response"], rates.sentinel_rate)
    coverage = inject_sentinels(rng, cats["Coverage"], rates.sentinel_rate * 0.8)
    education = maybe_null_strings(rng, cats["Education"], rates.mcar_null_rate * 1.2)
    vsize = maybe_null_strings(rng, cats["Vehicle Size"].astype(object), rates.mcar_null_rate * 1.1)
    sales_ch = maybe_null_strings(rng, cats["Sales Channel"].astype(object), rates.mcar_null_rate * 1.0)

    # Income_raw optional comma string
    income_raw: list[str | None] = [None] * size
    fill_idx = np.where((rng.random(size) < rates.income_raw_fill_rate) & ~np.isnan(income_f))[0]
    for i in fill_idx:
        income_raw[i] = f"{income_f[i]:,.2f}"

    # MCAR on last_campaign_response etc
    last_resp = maybe_null_strings(rng, last_resp.astype(object), rates.mcar_null_rate * 0.9).astype(object)
    channel_pref = maybe_null_strings(rng, cats["channel_preference"].astype(object), rates.mcar_null_rate * 1.1).astype(object)

    # Assemble columns
    data: dict[str, object] = {
        "customer_id": customer_id,
        "campaign_id": campaign_id,
        "campaign_month": campaign_month,
        "campaign_channel": cats["campaign_channel"],
        "channel_preference": channel_pref,
        "last_campaign_response": last_resp,
        "days_since_last_campaign": days_since,
        "number_of_previous_campaigns": n_prev.astype(np.float64),
        "offer_type": cats["offer_type"],
        "region_cluster": cats["region_cluster"],
        "Customer": cats["Customer"],
        "State": states,
        "Response": response.astype(object),
        "Coverage": coverage,
        "Education": education,
        "EmploymentStatus": cats["EmploymentStatus"],
        "Gender": gender,
        "Location Code": cats["Location Code"],
        "Marital Status": cats["Marital Status"].astype(object),
        "Policy Type": cats["Policy Type"],
        "Policy": cats["Policy"],
        "Renew Offer Type": cats["Renew Offer Type"],
        "Sales Channel": sales_ch,
        "Vehicle Class": vcls,
        "Vehicle Size": vsize,
        "Customer Lifetime Value": clv,
        "Income": income_f,
        "Monthly Premium Auto": premium,
        "Months Since Last Claim": months_claim,
        "Months Since Policy Inception": months_incept,
        "Number of Open Complaints": complaints.astype(np.float64),
        "Number of Policies": n_policies.astype(np.float64),
        "Total Claim Amount": claim_amt,
        "Effective To Date": eff_dates,
        "marketing_company": templates["marketing_company"][tmpl_idx],
        "marketing_campaign_type": templates["marketing_campaign_type"][tmpl_idx],
        "marketing_channel_used": templates["marketing_channel_used"][tmpl_idx],
        "marketing_clicks": templates["marketing_clicks"][tmpl_idx].astype(np.int64),
        "marketing_impressions": templates["marketing_impressions"][tmpl_idx].astype(np.int64),
        "marketing_eng_score": templates["marketing_eng_score"][tmpl_idx].astype(np.int64),
        "marketing_market_segment": templates["marketing_market_segment"][tmpl_idx],
        "marketing_conversion_rate_str": templates["marketing_conversion_rate_str"][tmpl_idx],
        "marketing_roi_str": templates["marketing_roi_str"][tmpl_idx],
        "marketing_acquisition_cost": templates["marketing_acquisition_cost"][tmpl_idx].astype(np.int64),
        "marketing_target_audience": templates["marketing_target_audience"][tmpl_idx],
        "marketing_language": templates["marketing_language"][tmpl_idx],
        "campaign_cohort_key": np.array([f"COH-{int(i):05d}" for i in tmpl_idx], dtype=object),
        "Age": age,
        "Income_raw": income_raw,
    }

    df = pl.DataFrame(data)

    for col in df.columns:
        if df[col].dtype != pl.Object:
            continue
        if col == "Age":
            df = df.with_columns(pl.col(col).cast(pl.Float64, strict=False))
        else:
            df = df.with_columns(
                pl.col(col)
                .map_elements(
                    lambda x: None
                    if x is None
                    else (None if isinstance(x, float) and bool(np.isnan(x)) else str(x)),
                    return_dtype=pl.String,
                )
                .alias(col)
            )

    if dup_n > 0:
        dup_idx = rng.choice(np.arange(size), size=dup_n, replace=True)
        dup_df = df[dup_idx]
        df = pl.concat([df, dup_df], how="vertical")

    return df


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Generate synthetic messy insurance+marketing Parquet dataset.")
    p.add_argument("--out", type=str, default="synthetic_insurance_marketing_2m", help="Output directory")
    p.add_argument("--n", type=int, default=TOTAL_ROWS_DEFAULT, help="Total output rows (including exact duplicates)")
    p.add_argument("--seed", type=int, default=42, help="Base RNG seed")
    p.add_argument(
        "--chunk-rows",
        type=int,
        default=200_000,
        help="Target rows per Parquet part file (primary+dup within each part)",
    )
    p.add_argument("--n-templates", type=int, default=10_000, help="Marketing template catalog size")
    p.add_argument(
        "--exact-dup-rate",
        type=float,
        default=DefectRates.exact_dup_row_rate,
        help="Fraction of rows appended as exact duplicates per chunk",
    )
    return p.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry: write chunked Parquet parts under ``--out``."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    args = parse_args(argv)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    rates = DefectRates(exact_dup_row_rate=args.exact_dup_rate)
    rng = np.random.default_rng(args.seed)
    templates = build_marketing_templates(rng, n_templates=args.n_templates)

    total_target = args.n
    chunk_rows = max(10_000, args.chunk_rows)
    n_templates = args.n_templates
    dup_rate = max(0.0, rates.exact_dup_row_rate)

    written = 0
    part = 0
    global_start = 0
    remaining = total_target

    while remaining > 0:
        chunk_out = min(chunk_rows, remaining)
        if dup_rate <= 0.0:
            inner = chunk_out
            dup_n = 0
        else:
            inner = max(1, int(round(chunk_out / (1.0 + dup_rate))))
            dup_n = max(0, chunk_out - inner)

        logger.info(
            "Generating part=%s global_start=%s primary=%s dup=%s (chunk_out=%s)",
            part,
            global_start,
            inner,
            dup_n,
            chunk_out,
        )
        df = generate_chunk(
            global_start=global_start,
            size=inner,
            dup_n=dup_n,
            seed=args.seed,
            templates=templates,
            n_templates=n_templates,
            rates=rates,
        )
        path = out_dir / f"part-{part:04d}.parquet"
        df.write_parquet(path, compression="zstd")
        out_rows = len(df)
        written += out_rows
        logger.info("Wrote %s rows -> %s", out_rows, path)
        part += 1
        global_start += inner
        remaining -= out_rows

    logger.info("Done. Total rows written=%s", written)
    # sidecar metadata
    meta = out_dir / "generation_meta.txt"
    meta.write_text(
        f"n_target_rows={total_target}\n"
        f"chunk_rows={chunk_rows}\n"
        f"seed={args.seed}\n"
        f"n_templates={n_templates}\n"
        f"exact_dup_rate={dup_rate}\n"
        f"total_rows_written={written}\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
