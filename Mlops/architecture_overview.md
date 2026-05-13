# Modernized Marketing Prediction Architecture
## Franklin Madison Group

### 1. Executive Summary
The goal of this architecture is to replace the legacy, fragmented pipeline (which relied on manual data transfers between a Data Warehouse, SAS, and AWS VMs) with a unified, scalable, and automated **Databricks Lakehouse**. This new system is specifically designed to handle 100-200 million records seamlessly and provide live predictive insights directly to the marketing team.

---

### 2. The End-to-End Workflow (Medallion Architecture)

The pipeline is structured using the industry-standard "Medallion Architecture" ensuring data quality, scalability, and strict governance.

#### Phase 1: Data Ingestion (Bronze Layer)
*   **What happens:** Raw data (campaign details, customer demographics, response data) is ingested from cloud storage (like AWS S3 or Redshift) exactly as it arrives. 
*   **Tool Used:** Databricks Auto Loader (`cloudFiles`).
*   **Deep Dive on Auto Loader:** Auto Loader acts as an intelligent watchman for cloud storage. Instead of re-reading millions of historical rows every time a pipeline runs, Auto Loader tracks a `checkpointLocation`. When "once in a while" data updates drop into S3, it only grabs the brand new files and appends them to the Bronze Delta table.
    *   *Cost Efficiency:* By using `.trigger(availableNow=True)`, Auto Loader acts as a streaming batch job—it turns on, processes new files, and immediately shuts down the cluster to save money.
    *   *Schema Evolution:* It automatically detects if new columns are added to the source CSVs and safely appends them without breaking the pipeline.
*   **Purpose:** To maintain an immutable, historical record of all raw data before any changes are made, with zero manual state management.

#### Phase 2: Data Preparation & Cleaning (Silver Layer)
*   **What happens:** **This replaces the legacy SAS data processing.** The raw data is cleaned, duplicates are removed, null values are handled, and customer demographic tables are joined with campaign response tables.
*   **Tool Used:** PySpark on Databricks.
*   **Purpose:** To create a "single source of truth" (`silver_marketing_campaigns`) that is highly structured and ready for machine learning.

#### Phase 3: Machine Learning & Modeling
*   **What happens:** **This replaces the legacy AWS VM Live Modeling.** The clean Silver data is fed into a machine learning algorithm to learn patterns of customer retention and churn.
*   **Tools Used:** 
    *   **Spark MLlib:** Used to train a Random Forest classification model. Spark MLlib is specifically designed to distribute the math across a cluster of computers, easily handling 200M+ rows.
    *   **MLflow:** Automatically tracks the model's accuracy, parameters, and saves the model artifact so it can be audited, reproduced, or promoted to production later.
*   **Purpose:** To generate the AI model that accurately predicts whether a customer will Stay (1) or Drop (0).

#### Phase 4: Batch Scoring (Gold Layer)
*   **What happens:** The trained production model is applied to the current list of customers. It generates a specific mathematical probability score for every single customer.
*   **Tool Used:** PySpark & MLflow.
*   **Purpose:** To output a highly optimized, business-ready table containing the final predictions (`gold_marketing_predictions`).

#### Phase 5: Dashboarding & Business Intelligence
*   **What happens:** The Gold table (predictions) and Silver table (customer details) are linked visually to create interactive charts, such as "Stay vs. Drop" ratios and "High-Risk Customer Action Lists".
*   **Tools Used:** Microsoft Power BI.
*   **Purpose:** To give the Franklin Madison marketing team a no-code, always-up-to-date interface to make immediate decisions on campaign targeting.

---

### 3. Summary of Core Technologies Used

| Tool / Technology | Role in the Pipeline | Why we are using it |
| :--- | :--- | :--- |
| **Databricks** | The Core Platform | Provides a single unified environment, entirely eliminating the need to move massive datasets between external tools (like SAS and VMs). |
| **Delta Lake** | Storage Format | The underlying format for the Bronze, Silver, and Gold tables. It allows for ACID transactions, version history, and handles massive data volumes with high read/write speeds. |
| **Databricks Auto Loader** | Ingestion Engine | Automatically tracks and ingests only *newly* arrived data files in cloud storage, saving massive compute costs and eliminating manual state management. |
| **PySpark** | Compute Engine | The coding language used for data prep and modeling. It distributes the data processing across multiple computers, making it infinitely scalable. |
| **MLflow** | MLOps Tracking | Replaces manual model tracking. It acts as a central repository for "Production" models and automatically logs all metrics (like AUC and Accuracy). |
| **Databricks Serverless** | Infrastructure | Automatically spins up compute resources instantly when code runs, and scales down to zero when finished, saving costs while completely avoiding "out of memory" errors. |
| **Power BI** | BI & Presentation | Replaces static, manual reports. It provides interactive, visual analytics for business stakeholders. |
| **DirectQuery** | Connectivity | Ensures Power BI queries the Databricks cluster directly rather than downloading 100M+ rows to a local laptop. The dashboard is never out-of-sync with the database. |

---

### 4. Databricks tools — same order as the pipeline (ingestion first, then each stage in detail)

Read **top to bottom**. Each numbered subsection matches the **medallion flow**: ingest → Silver → train → govern model → score → serve SQL → wrap with orchestration, governance, and optional add-ons.  
For every **Databricks** (or Databricks-hosted) capability below: **what it is**, **what we use it for here**, **how it helps**.

---

#### 4.1 Topic — Ingestion and raw landing (Bronze)

**Business goal:** Bring campaign, customer, response, and third-party feeds from **AWS S3** (and/or **Redshift**-backed patterns) into the lakehouse **incrementally**, without reprocessing all history every night, and store an **immutable raw copy** for audit and replay.

| Capability | What it is | What we use it for (marketing prediction) | How it helps |
|------------|------------|-------------------------------------------|--------------|
| **Lakehouse (pattern on Databricks)** | One platform where **low-cost object storage** meets **ACID tables** and **Spark/SQL** processing—no separate “data lake” vs “warehouse” silos. | Landing **Bronze** tables in the **same** workspace where Silver/ML/Gold run. | Fewer handoffs than legacy “S3 + VM + warehouse”; one place for pipelines and governance. |
| **Databricks Workspace** | Web UI + APIs: notebooks, jobs, data explorer, SQL, MLflow. | Build and operate the **ingest** notebook/job; browse Bronze tables. | Team collaboration, scheduling, and monitoring in one product. |
| **Delta Lake** | Open table format: ACID transactions, scalable files, time travel, schema evolution hooks. | **Bronze Delta tables** = append-only (or controlled) raw landing from Auto Loader. | Safe concurrent writes; **replay Silver** from Bronze if logic changes; history for compliance. |
| **Auto Loader (`cloudFiles`)** | Spark Structured Streaming source that tracks which files/objects were already ingested. | Read **new** files under an S3 prefix; write to **Delta Bronze**. | **Checkpoints** avoid full bucket rescans → **lower cost** and faster incremental runs. |
| **Checkpoint location** | Durable metadata path (often in cloud storage) storing ingestion progress. | One checkpoint path per ingest pipeline. | Exactly-once style progress; **reprocess** or **resume** without guessing which files ran. |
| **Schema evolution / rescue** | Options to merge or rescue unexpected columns when source files change. | When marketing feeds add columns without notice. | Pipelines **do not hard-fail** on new CSV columns; you review then tighten schema in QA. |
| **Trigger: available now (micro-batch)** | Process all currently available new data then stop the streaming query. | Scheduled “**land what arrived**” jobs instead of always-on streams. | **Cluster spins down** after work—matches periodic file drops and saves money. |
| **Spark cluster / Serverless compute for jobs** | Executors that run the Auto Loader query. | Attach a **job cluster** or **serverless** compute to the ingest job. | Enough CPU/memory to parse large files; autoscale for spikes. |
| **Unity Catalog — external locations & storage credentials** | UC objects that define **which cloud paths** are readable/writable and **which identity** may access them. | Register the **S3 landing prefix** and checkpoint path under governance. | **Least-privilege** access to buckets; auditable **who read which path**. |
| **COPY INTO (Delta, SQL)** | Idempotent SQL statement to load files from a path into a Delta table. | Alternative to Auto Loader when ops prefer **pure SQL** loads for some feeds. | Simple SQL operations; different trade-offs vs Auto Loader on incremental discovery. |
| **Notebook or Job task** | Notebook code packaged as a **Workflow** task with retries. | Production ingest runs as a **job**, not a manual notebook click. | Repeatable, alertable, parameterized runs. |

*External (not Databricks) but required for this topic:* **Amazon S3** (landing files), **IAM / instance profile or service principal** so Databricks can read S3; optionally **Redshift unload → S3** if warehouse feeds files for Auto Loader.

---

#### 4.2 Topic — Preparation and curated layer (Silver)

**Business goal:** Replace legacy **SAS** prep: standardize types, enforce quality, dedupe, join dimensions, and output **one ML-ready table** (e.g. `silver_marketing_campaigns`).

| Capability | What it is | What we use it for | How it helps |
|------------|------------|-------------------|----------------|
| **Apache Spark — PySpark & Spark SQL** | Distributed DataFrame/SQL engine on Databricks. | Read **Bronze Delta**; apply transforms; write **Silver Delta**. | Scales to **100M–200M+** rows; same engine as ingest and scoring—skills transfer. |
| **Delta Lake (Silver tables)** | ACID curated tables; supports `MERGE`, constraints (where used), time travel. | Materialize **silver_marketing_campaigns** at agreed **grain** (e.g. customer × campaign). | **MERGE** supports incremental upserts; time travel helps debug “why did this row change.” |
| **Delta `MERGE`** | Upsert pattern matching keys and updating/inserting rows. | Refresh Silver when late-arriving facts appear without full overwrite. | Correct incremental **SLAs** without double-counting. |
| **Photon (optional)** | Native vectorized execution for parts of Spark SQL/DataFrame API. | Turn on for heavy Silver SQL if benchmarks show gain. | Can reduce runtime and cost on large scans/joins (when compatible). |
| **Table constraints & expectations (optional)** | CHECK / NOT NULL / Delta Expectations or DLT expectations. | Enforce “response flag in {0,1}” style rules on Silver writes. | Catch bad data **before** training poisons the model. |
| **`OPTIMIZE` / Z-order / liquid clustering (optional)** | File compaction and data skipping hints. | After large Silver loads, tune files for training filter columns. | Faster reads for repeated training and scoring reads. |
| **Unity Catalog** | Catalog.schema.table naming; grants on tables/columns. | `GRANT SELECT` on Silver to data science group; lock PII columns where needed. | **Column-level** and **table-level** security for regulated fields. |
| **Databricks Notebooks** | Interactive Spark development. | Build and test Silver logic; then productionize as a **Job**. | Fast iteration; same code path promoted to scheduled jobs. |

---

#### 4.3 Topic — Model training (distributed ML)

**Business goal:** Learn **Stay vs Drop** from Silver history at scale (Random Forest or similar distributed algorithm).

| Capability | What it is | What we use it for | How it helps |
|------------|------------|-------------------|----------------|
| **Databricks Runtime ML** | Spark runtime image with common ML/Python libs for data science. | Cluster type for **training** notebooks/jobs. | Fewer “missing library” issues; tested combinations for Spark + ML. |
| **Spark MLlib** | Distributed ML algorithms and **Pipeline** API (`VectorAssembler`, `StringIndexer`, `RandomForestClassifier`, etc.). | Fit a **classification** model on full Silver training slice. | Uses **all executors**—no single-node RAM ceiling for 200M+ rows. |
| **MLflow Tracking** | Per-run logging of params, metrics, artifacts. | Log `numTrees`, depth, train/val **AUC**, confusion artifacts each experiment. | **Reproducibility** and leader-board comparison across tries. |
| **Train / test split by time or campaign (pattern)** | Not a separate “tool” but a best practice in Spark. | Avoid random splits that **leak future** into past for time-ordered marketing outcomes. | Models that generalize to **next month’s** behavior, not inflated offline accuracy. |

---

#### 4.4 Topic — MLOps and model governance (which build is “Production”?)

**Business goal:** Only **one approved** model version is used in scoring; auditors can trace **who promoted what when**.

| Capability | What it is | What we use it for | How it helps |
|------------|------------|-------------------|----------------|
| **MLflow Model Registry** | Versioned models with **Staging / Production** (and custom) stages. | Register the trained MLlib pipeline; transition winner to **Production** after sign-off. | Scoring job always resolves **Production** URI—no “wrong pickle on share drive.” |
| **Unity Catalog + registered models (when enabled)** | UC can govern **model assets** alongside tables. | Grant only the **scoring job principal** permission to read Production model. | Same governance plane as **Silver/Gold** tables. |
| **Model signature / input schema** | MLflow model flavor metadata describing required columns/types. | Validate scoring DataFrame matches training features. | **Fails fast** if Silver schema drifts from what the model expects. |

---

#### 4.5 Topic — Batch scoring and predictions (Gold)

**Business goal:** Write **one row per customer** (or agreed grain) with **probability / label** and audit fields into `gold_marketing_predictions`.

| Capability | What it is | What we use it for | How it helps |
|------------|------------|-------------------|----------------|
| **PySpark** | Distributed transforms. | Load **Production** MLflow model; `transform` Silver (or feature) DataFrame; write **Gold**. | Same scale story as training—full population in one batch window. |
| **MLflow model load** | Load registered Spark model by name/version/stage. | Scoring job pulls **Production** artifact. | **Tight coupling** between governance and runtime. |
| **Delta Lake (Gold)** | ACID Gold tables. | `MERGE` predictions by business key; add `scored_at`, `model_version`, `run_id`. | **Idempotent** reruns; marketing sees consistent keys; audit trail. |

---

#### 4.6 Topic — SQL access, warehouses, and BI connectivity

**Business goal:** Marketing and analysts query **Gold/Silver** through SQL without copying 100M+ rows to desktops.

| Capability | What it is | What we use it for | How it helps |
|------------|------------|-------------------|----------------|
| **Databricks SQL** | SQL workspace + query history + dashboards (optional). | Ad hoc validation queries; optional **Lakeview** dashboards. | Fast SQL on lakehouse tables without Spark notebook for every question. |
| **SQL warehouse** | Dedicated SQL compute (serverless or classic) sized for concurrency. | **Power BI DirectQuery** connection target; shared semantic queries. | Isolates BI load from heavy Spark ETL clusters; **governs cost** with T-shirt sizes. |
| **Partner connectivity (JDBC/ODBC / native connector)** | Official drivers and **Power BI** connector to Databricks SQL. | Connect Power BI to warehouse; use **DirectQuery** mode. | Dashboards stay **live** against Gold; no huge **Import** dataset on laptops. |

*External:* **Microsoft Power BI** is not Databricks; it **consumes** Databricks SQL through the connector above.

---

#### 4.7 Topic — Orchestration, scheduling, and operations

**Business goal:** Run ingest → Silver → (train on cadence) → score **on a schedule** with dependencies, retries, and alerts.

| Capability | What it is | What we use it for | How it helps |
|------------|------------|-------------------|----------------|
| **Databricks Workflows (Jobs)** | DAG of tasks: notebooks, JARs, Python wheel tasks, dbt, SQL, etc. | Chain Bronze ingest → Silver → train → score with **depends on**. | **End-to-end automation**; clear failure surface; parallel branches when safe. |
| **Job parameters** | Key-value inputs to each run. | Pass `run_date`, `catalog`, `model_name` into notebooks. | Same code, **multiple environments** (dev/QA/prod). |
| **Job clusters / policy / pools** | Ephemeral clusters created per job run under admin policy. | Right-size Spark for each stage; enforce tags (`cost_center=marketing`). | **Cost control** and standard hardware. |
| **Serverless job / notebook compute** | Databricks-managed sizing for supported workloads. | Same tasks without manual driver/worker tuning where available. | Faster time-to-production for teams new to cluster sizing. |
| **Notifications & webhooks** | Job failure / duration alerts. | Page on-call when ingest or scoring fails so marketing does not use stale Gold. | Operational reliability. |

---

#### 4.8 Topic — Security, secrets, and engineering hygiene

**Business goal:** No passwords in notebooks; least privilege; auditable access.

| Capability | What it is | What we use it for | How it helps |
|------------|------------|-------------------|----------------|
| **Secrets (scopes)** | Encrypted secret storage integrated with cloud key vaults. | Store JDBC strings, API keys for external enrichments. | **No secrets in Git**; rotation without code edits. |
| **Service principals & PAT / OAuth** | Non-human identities for jobs and automation. | Production jobs and CI use SP; humans use SSO. | Clear **audit** trail for automated writes to Gold. |
| **Repos (Git integration)** | Git-backed projects in workspace. | Version Silver/ML/score notebooks; PR review before prod deploy. | **Change control** aligned to enterprise Git. |
| **Audit logs & lineage (Unity Catalog)** | Who accessed which table/model; column lineage in UI. | Prove compliance for PII in Silver; trace Gold column to Silver sources. | Regulators and internal risk teams get **evidence**. |

---

#### 4.9 Topic — Optional Databricks tools (use when complexity grows)

| Capability | When to add it | What it adds |
|------------|----------------|----------------|
| **Databricks Feature Store** | Many feature sets reused across models and online/offline paths. | One **registered** definition of features—reduces train–serve skew. |
| **Delta Live Tables (DLT)** | You want declarative pipelines + built-in expectations as first-class. | Pipeline DAG + data quality in product vs only custom PySpark checks. |
| **Lakehouse Monitoring** | You need automated drift/freshness alerts on Silver/Gold. | Proactive detection before marketing sees wrong charts. |
| **Model Serving (real-time)** | You need HTTP scoring separate from nightly Gold batch. | Online channel scores without Spark batch latency. |
| **dbt on Databricks** | Analysts prefer dbt for some Silver marts. | SQL-first transformations with tests—coexists with PySpark. |

---

#### 4.10 One-page order checklist (matches §2 phases)

1. **Ingestion (Bronze)** — Lakehouse + **Delta** + **Auto Loader** + checkpoints + (optional **COPY INTO**) + **UC** paths + **Job compute**.  
2. **Silver** — **PySpark/SQL** + **Delta MERGE** + (optional **Photon**/optimize) + **UC** grants.  
3. **Train** — **ML Runtime** + **MLlib** + **MLflow Tracking**.  
4. **Govern** — **MLflow Registry** (+ **UC** models).  
5. **Score (Gold)** — **PySpark** + **MLflow Production model** + **Delta MERGE**.  
6. **Serve** — **Databricks SQL** + **SQL warehouse** + **Power BI DirectQuery**.  
7. **Wrap** — **Workflows**, clusters/serverless, **secrets**, **Repos**, **audit**.

This section is the **expanded tool list** in **pipeline order**; **§2** remains the short narrative; **§3** remains the compact summary table.
