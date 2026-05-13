# Marketing proto pipeline (Databricks) — SD + STAT → MRGAL → sample prep + responders

**Source of truth:** keep notebooks and `databricks.yml` in **Git**; use **Databricks Repos** (and/or **bundle deploy** from a Git clone). See [Git-first workflow](#git-first-workflow) below.

This bundle implements a **small end-to-end** flow matching the FMG diagram **through batch scoring**:

1. **Ingest** SD driver + multiple STAT Parquet files + responders from a **single folder** (DBFS, **Unity Catalog Volume**, or `s3a://…` if the cluster can read it).
2. **Auto MRGAL** — join all STAT snapshots onto the SD grain on **`pit_key`**.
3. **Auto sample prep** — left-join **responders**; derive `responder_joined` flag.
4. **Train** — **product-specific** baseline **sklearn** model (filter by `product_line`) + **MLflow** (prototype scale; swap for Spark ML for production volume).
5. **Validate** — AUC / PR-AUC on holdout for the same `product_line` slice, using the latest MLflow run for that line.
6. **Recommendations** — stub table (extend later).
7. **Score** — write `gold_scored` with `prediction_prob` filled only for rows whose `product_line` matches the job parameter; other lines stay null (child model only touches its slice).

## Product-specific (child) models

**Accident & Illness supplemental** portfolio (fixture alignment):

| `product_line` (job parameter) | Sub-product |
|--------------------------------|-------------|
| `HOSPITAL_ACCIDENT` | Hospital Accident Insurance — daily hospital cash during accident hospitalization |
| `RECUPERATIVE_CARE` | Recuperative Care Plan — recovery from illness or accident; pre-existing; no waiting period |
| `ACCIDENT_EXPENSE` | Accident Expense Coverage — lump-sum for burns, fractures, sports injuries, dislocations, cuts |
| `CRITICAL_ILLNESS` | Critical Illness & Injury — lump-sum for cancer, stroke, heart attack, paralysis, coma |

Aligned with the modeling transcript: a **parent** model on all products can be added later; this proto implements the **child / sister** path — one model **per `product_line`** trained only on that line’s samples.

- Fixture column **`product_line`**: codes above (on `sd_driver` and `responders`). **`offer_type`** matches the display name for the same row.
- Parameter **`product_line`** (default `HOSPITAL_ACCIDENT`): use the same value across **04 → 05 → 07** in one job run (`databricks.yml` variable `product_line`).
- **`gold_proto_train_metadata`** uses **append**; each train adds a row with `product_line` + `mlflow_run_id`. Validation and scoring pick the **latest** row for the requested `product_line`.
- To train another line, re-run the pipeline with a different `product_line` (for example `CRITICAL_ILLNESS`).

## Fixtures (SD / STAT / responders)

Generated locally by:

```bash
py -3 scripts/generate_sd_stat_fixtures.py --out databricks/proto/fixtures --n 8000
```

| File | Role |
|------|------|
| `sd_driver.parquet` | **Score driver** — one row per `(customer_id, campaign_id)` plus **`product_line`** |
| `stat_promotion.parquet` | **STAT** — promotion-style attributes |
| `stat_membership.parquet` | **STAT** — membership attributes |
| `stat_demographics.parquet` | **STAT** — demographics (≈97% rows: simulates late/missing keys) |
| `responders.parquet` | **Responders append** — positive keys only (includes **`product_line`**) |

Generate or refresh fixtures from repo root:

```bash
py -3 scripts/generate_sd_stat_fixtures.py --out databricks/proto/fixtures --n 8000
```

**Join key (all files):** `pit_key` = `customer_id || campaign_id` (literal string with `||`).

### Upload fixtures to Databricks

Pick **one**:

**A — DBFS (quick dev)**  
Upload the contents of `databricks/proto/fixtures/*.parquet` to e.g.  
`/FileStore/marketing_proto_fixtures/`  
Then set widget **`fixture_base`** = `/dbfs/FileStore/marketing_proto_fixtures` (no trailing slash).

**B — Unity Catalog Volume (preferred)**  
Copy the same files into a Volume path and set **`fixture_base`** to that **`/Volumes/catalog/schema/volume/path`** root.

**C — S3**  
Upload to your bucket prefix. Configure **instance profile** or **UC external location** + **storage credential** — **do not** put AWS keys in notebook widgets. Set **`fixture_base`** = `s3://bucket/prefix` (Spark will use `s3://` or `s3a://` per your cluster config).

## Unity Catalog prep (once)

```sql
CREATE CATALOG IF NOT EXISTS main;  -- or your dev catalog name
CREATE SCHEMA IF NOT EXISTS main.marketing_proto_bronze;
CREATE SCHEMA IF NOT EXISTS main.marketing_proto_silver;
CREATE SCHEMA IF NOT EXISTS main.marketing_proto_gold;
```

Use the same names in the job **parameters** / notebook widgets (`catalog`, `*_schema`).

## Git-first workflow

Keep **this repo as the source of truth** in Git (GitHub, GitLab, Azure DevOps, etc.), then attach Databricks to that repo.

1. **Push the repo**  
   Commit and push `DataHub-Models` (including `databricks/proto/` notebooks and `databricks.yml`) to your remote.

2. **Databricks Repos**  
   In the workspace: **Workspace → Repos → Add repo** (or **Git folders** per your admin setup). Paste the **HTTPS or SSH** clone URL, pick a branch (e.g. `main`), and clone.  
   You will get a path like `/Repos/<user>/DataHub-Models` (exact path depends on workspace).

3. **Run notebooks from Git**  
   Open tasks from the Repo tree, for example:  
   `Repos/.../DataHub-Models/databricks/proto/src/01_s3_discover_ingest.py` through `07_batch_score.py`.

4. **Jobs (Workflows)**  
   - **Option A — Job points at Repo notebooks:** create a multi-task job whose notebook paths are the **Repo** paths above. Use the same **base parameters** as in `databricks.yml` (`catalog`, `*_schema`, `fixture_base`, `run_id`, `product_line`).  
   - **Option B — Bundle deploy from Git checkout:** on your laptop or in **CI**, clone the repo, `cd databricks/proto`, run `databricks bundle deploy`. That syncs job definitions into the workspace while **code stays authored in Git**; redeploy after merges.

5. **Branches**  
   Use feature branches in Git; open a second Repo checkout for a branch, or pull in Repos after merge. Avoid editing only in the workspace without committing back to Git.

6. **Fixtures and Git**  
   Generated `*.parquet` under `databricks/proto/fixtures/` can be large. Many teams **do not commit** them: add `databricks/proto/fixtures/*.parquet` to `.gitignore`, store artifacts in a **Volume** or **S3**, and generate them in CI or a one-off notebook. If you do commit them, consider **Git LFS** for your org’s policy.

### Databricks still shows `Mlops/`, `scripts/`, or other removed folders?

On GitHub, **`main` only contains** `README.md`, `.gitignore`, and `databricks/proto/**`. If Databricks still shows the old tree, you are on a **stale clone** or not inside **Repos**.

1. **Confirm on GitHub** (browser): open `https://github.com/gagan-600/DataHub-Models` → branch **`main`** → you should see **only** those paths (no `Mlops/`, no `scripts/`).
2. **Open the Git copy, not Workspace uploads:** left sidebar **Workspace → Repos** (or **Catalog → Git folders**) → your **DataHub-Models** repo. Do **not** use an old folder under **Workspace** where you may have uploaded the full project earlier.
3. **Pull latest:** in the Repo, open the **branch** menu → **Pull** (or **Sync**). If there is no pull, **remove** this Git folder / Repo link and **Add repo** again with `https://github.com/gagan-600/DataHub-Models.git` on branch **`main`**.
4. **Optional — sparse checkout:** when creating the Git folder, enable **sparse checkout** and set the path to **`databricks/proto`** so only that directory is checked out (useful if the repo grows again later).

## Deploy the job (Databricks Asset Bundles)

Install the CLI once (pick one):

```bash
pip install databricks-cli
# or (newer): pip install databricks-bundles
```

From the **Git clone** of this repo (local machine or CI agent):

```bash
cd databricks/proto
databricks bundle validate
databricks bundle deploy --target dev
```

If your workspace is not linked yet, set `host` in `databricks.yml` under `targets.dev.workspace`, or run `databricks configure`.

**Manual alternative:** import from **Repos** (same paths as in Git) *or* copy the seven notebooks under `src/` into a workspace folder, create a **Workflow** with tasks in order `01` → … → `07`, and paste the same **parameters** the bundle would pass.

## Parameters (widgets / job parameters)

| Key | Example | Meaning |
|-----|---------|--------|
| `catalog` | `main` | UC catalog |
| `bronze_schema` | `marketing_proto_bronze` | Bronze tables |
| `silver_schema` | `marketing_proto_silver` | Silver tables |
| `gold_schema` | `marketing_proto_gold` | Gold tables |
| `fixture_base` | `/dbfs/FileStore/marketing_proto_fixtures` | Folder with Parquet files |
| `run_id` | `2026-05-13-001` | Lineage column |
| `product_line` | `HOSPITAL_ACCIDENT` | **Product-specific model slice** — must match train / validate / score (`HOSPITAL_ACCIDENT`, `RECUPERATIVE_CARE`, `ACCIDENT_EXPENSE`, `CRITICAL_ILLNESS` in fixtures) |

## Security note

Do **not** embed long-lived **AWS access keys** in notebooks. Use **IAM instance profile**, **OIDC federation**, or **Unity Catalog external locations**.

## Outputs (Delta tables)

| Step | Table |
|------|--------|
| 01 | `{catalog}.{bronze_schema}.bronze_sd_driver`, `bronze_stat_promotion`, `bronze_stat_membership`, `bronze_stat_demographics`, `bronze_responders` |
| 02 | `{catalog}.{silver_schema}.silver_mrgal_universe` |
| 03 | `{catalog}.{silver_schema}.silver_sample_base` |
| 04 | `{catalog}.{gold_schema}.gold_proto_train_metadata` (append; includes `product_line`) |
| 05 | `{catalog}.{gold_schema}.gold_validation_metrics` |
| 06 | `{catalog}.{gold_schema}.gold_recommendations_stub` |
| 07 | `{catalog}.{gold_schema}.gold_scored` |

## Phase 2 (not in notebooks)

LOL generation, manual name selection, SO file parity load-back to warehouse — add as tasks once file specs are known.
