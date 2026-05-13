# Platform comparison & recommendation  
## Franklin Madison — marketing lakehouse (100–200M+ records)

**Purpose:** Pick a primary platform for ingest → prep → train → score → BI, with minimal glue code and clear governance.

**Disclaimer:** Guidance for architecture discussions — not a procurement quote. Validate licensing and SLAs with vendor and cloud teams.

**Assumptions (read this first — avoids overstating facts)**

- This note is **qualitative**: no benchmark scores, no pricing, no performance timings. “Strong / weak fit” means **fit to the FMG lakehouse story** in internal docs (Spark, Delta-style layers, MLflow, orchestration), **not** universal product rankings.
- **Vendor features change.** Confirm connectors (e.g. Power BI ↔ Databricks SQL), SKUs, and governance capabilities on **current** vendor documentation before procurement.
- **Medallion** (Bronze/Silver/Gold) is an **industry pattern**; Delta Lake is an **open table format** also usable outside Databricks (e.g. EMR). Phrases like “Databricks + Delta” refer to **that vendor’s integrated product**, not exclusive ownership of the format.

**How to present:** Use **Section 3** for **advantages vs disadvantages** (all options on one slide, or one row per slide). Use **Section 4** for a quick **fit snapshot**; **Section 5** for recommendation and governance questions.

---

## 1. What we need (context)

| Area | Requirement |
|------|-------------|
| **Scale** | ~100–200M rows — distributed prep, training, batch scoring. |
| **Lakehouse** | Bronze / Silver / Gold on **Delta** (or equivalent). |
| **Ingest** | Incremental loads from **S3** (and similar). |
| **Replace SAS / VMs** | **PySpark** ETL; **MLlib** + **MLflow**. |
| **BI** | **Power BI DirectQuery** (or SQL dashboards) — no huge extracts to laptops. |
| **Operations** | One orchestrated pipeline; governed tables; ephemeral compute where possible. |

---

## 2. Options (IDs)

| ID | Option | One-line description |
|----|--------|----------------------|
| **A** | **Databricks** | Spark, Delta, Auto Loader, MLflow, Workflows, Unity Catalog, SQL warehouse — one product family. |
| **B** | **AWS assembled** | S3 + Glue/EMR + Delta + SageMaker + Step Functions / Airflow — you wire the pieces. |
| **C** | **GCP assembled** | GCS + Dataproc + BigQuery + Vertex + Composer — same idea as B on Google Cloud. |
| **D** | **Microsoft Fabric / Synapse** | Strong Power BI + Microsoft governance; Spark/ML path depends on design / SKU. |
| **E** | **Snowflake-first** | Warehouse + SQL + BI strength; not Spark MLlib end-to-end by default. |
| **F** | **Snowflake + cloud ML** | Snowflake for data + SageMaker / Vertex / Azure ML — two domains to integrate. |

---

## 3. Presentation slide — advantages vs disadvantages (all options)

**Column meaning**

- **Advantages** = reasons this platform **may** fit FMG’s stated goals (not a guarantee for every org).
- **Disadvantages** = trade-offs or **misfits** vs an architecture that centers **Apache Spark**, **Delta-style lake tables**, **MLflow**, and **orchestrated jobs**. If your organization picks a **different** target architecture (e.g. warehouse-only), rescoring is required.

If your Markdown viewer shows raw tags, open this file in **VS Code Preview** or **GitHub** — line breaks use `<br>`.

| Option | **Advantages** | **Disadvantages** |
|--------|----------------|-------------------|
| **A — Databricks** | • Product stack aligns **well** with **Spark**, **Delta Lake on the platform**, **incremental ingest (e.g. Auto Loader)**, **MLflow**, **job orchestration (Workflows)**, and **SQL warehouses** for BI — fewer separate products than a fully custom assembly on **B/C** for the **same** pattern.<br>• **Unity Catalog** provides unified governance for **data** (and **models** when using supported MLflow / UC integrations — confirm current docs).<br>• **Power BI** can connect to **Databricks SQL** via Microsoft/Databricks-documented paths (validate connector for your tenancy).<br>• **Typically fewer integration projects** than wiring Glue + EMR + separate ML registry + orchestrator yourself — **not** a universal “always fastest”; depends on team skills.<br>• Spark distributes prep/scoring; **100–200M+** rows is a normal scale band for Spark **when** clusters are sized and tuned (not automatic). | • **Additional vendor** in the stack — procurement / InfoSec may require review.<br>• Commercial **lock-in** concerns vs cloud-native DIY (**B/C**).<br>• Internal mandates (**AWS-only**, **Fabric-first**, **Snowflake-only**) can override technical preference.<br>• Running **both** Snowflake and Databricks without clear boundaries can duplicate cost.<br>• Teams that prefer **full control** over every layer (e.g. EMR + self-hosted MLflow) may choose **B** deliberately. |
| **B — AWS assembled** | • Stays within **AWS** services (S3, Glue, EMR, SageMaker, Step Functions, MWAA, etc.) — satisfies policies that restrict **non-cloud or non-approved** SaaS (policy wording varies by company).<br>• Reuses common AWS building blocks and IAM patterns.<br>• **Apache Spark on EMR** can process **large** datasets; throughput depends on cluster sizing, partitions, and workload (same general engine family as Databricks, **not** identical performance).<br>• No **Databricks** subscription from this vendor. | • **You** integrate Glue, EMR, SageMaker, Lake Formation, orchestration, and observability — **many** handoffs unless a platform team owns it.<br>• Experiment tracking may split across **SageMaker Experiments**, self-hosted **MLflow**, etc., unless you **standardize** one.<br>• Time to a **repeatable** end-to-end pipeline varies with team maturity — often **longer** than a single integrated product **when** the team has not done this assembly before.<br>• **Power BI** to AWS query surfaces (Athena, Redshift, etc.) is **feasible** but requires explicit gateway/connector setup — not one bundled “Databricks SQL” experience.<br>• Higher **ongoing ops** burden than **A** for the **same** logical pipeline unless automation is mature. |
| **C — GCP assembled** | • Fits organizations standardized on **GCP** (billing, identity).<br>• **Dataproc** runs Spark; **BigQuery** handles large SQL; **Vertex AI** provides managed ML — all first-party Google services.<br>• No **Databricks** subscription from this vendor (unless you add it later). | • Same **multi-product integration** burden as **B** (e.g. Composer, IAM, networking).<br>• Organizations heavily invested in **Microsoft 365 / Power BI / Azure** may prefer **D** or **A** for simpler BI alignment — **organizational** fit varies.<br>• **Dataplex** and other governance tools require setup — not zero effort. |
| **D — Microsoft Fabric / Synapse** | • Strong alignment when the enterprise standard is **Microsoft** (Power BI, Entra ID, Purview / Fabric).<br>• Executive story of **“one Microsoft analytics stack”** can simplify approvals.<br>• Contracting may align with existing **Azure** agreements (**verify** your ELA). | • **Spark** pools, notebooks, and ML features **depend on product (Fabric vs Synapse) and SKU** — there is no single static recipe; confirm against **current** Microsoft docs.<br>• Internal FMG docs described here assume a **Databricks-like** pipeline; mapping to Fabric/Synapse requires **explicit** design (ingest, ML training, registry).<br>• Multiple Azure surfaces remain — complexity may or may not be lower than **A** depending on team skills.<br>• A **proof of concept** comparing cost, latency, and ML workflow to **A** is prudent before a large commitment. |
| **E — Snowflake-first** | • Strong for **SQL-centric** analytics, curated **warehouse** tables, and governance features Snowflake provides (see Snowflake docs for RBAC, masking, audit).<br>• **Power BI** connects to Snowflake via a **documented** connector path.<br>• **Snowpark** runs Python/SQL/Java workloads **inside** Snowflake’s engine — different from **Apache Spark** clusters.<br>• Compute **autosuspend** reduces idle warehouse cost compared to always-on clusters **when** workloads fit the warehouse model. | • **Apache Spark MLlib** on multi-node Spark is **not** Snowflake’s primary model; distributed ML often uses **Snowpark ML** or **pushdown** patterns — **different** skills and limits vs Spark MLlib at arbitrary cluster scale.<br>• A **lake-first Delta medallion** design (files + Delta on object storage as **spine**) differs from a **warehouse-first** design unless you explicitly integrate external tables / Iceberg — architecture choice, not “Snowflake wrong.”<br>• **Snowpipe** (continuous load) solves **incremental ingest** with different semantics than **Databricks Auto Loader** — migration requires design, not a rename.<br>• If FMG requires **unchanged** Spark MLlib training pipelines, **E alone** may force **architecture change** or adding **F/A/B** for Spark.<br>• Any “pick E vs A” decision should be validated with a **PoC** on real queries and ML workflows. |
| **F — Snowflake + cloud ML** (e.g. SageMaker / Vertex AI / Azure ML) | • Separates **warehouse / BI** (Snowflake) from **managed ML services** on AWS/GCP/Azure — common when org boundaries differ between **data platform** and **ML engineering**.<br>• Lets teams use **frameworks** and tooling native to each cloud ML service where Snowpark is not enough. | • **Two** vendors/cloud surfaces to secure, monitor, and pay for — integration is **required** (networking, IAM, data movement contracts).<br>• End-to-end orchestration spans **two** systems — more complex than **one** scheduler owning all tasks unless well automated.<br>• Risk of **ambiguous “system of record”** for scores unless keys, timestamps, and **model version** are enforced in **both** places.<br>• Not the **simplest** operating model if the goal is **one** platform for everything — only justified when constraints **require** both. |

**How to use this in a meeting**

- **One slide — compare all:** show the table above (columns **Advantages** | **Disadvantages**).
- **One slide per option:** copy **one row** (A, B, …) into a slide with two columns so the room focuses on a single letter.
- **Line breaks:** the table uses `<br>` between bullets. Use **VS Code / GitHub** preview, or paste into PowerPoint and replace `<br>` with new lines.

---

## 4. Snapshot — fit to this architecture (reference only)

**Subjective:** Rows below judge **alignment with FMG’s Spark-centric lakehouse assumptions** in this repo’s docs — **not** overall product quality.

| Option | Fit to FMG Spark lakehouse story | Integration effort | Suggested use |
|--------|----------------------------------|-------------------|----------------|
| **A** | **Highest among options listed** for that story | **Often lowest** glue vs multi-service **B/C** | Primary recommendation **for those assumptions** |
| **B / C** | Good **if** you invest in assembly | Usually **higher** than **A** | When policy favors DIY cloud stacks |
| **D** | Depends on Fabric/Synapse design — validate with PoC | Medium | Microsoft-first orgs |
| **E** | **Mixed** — strong warehouse/SQL; different path for Spark MLlib | Lower **for SQL-first** shops | Re-score if architecture shifts warehouse-first |
| **F** | Good **only if** hybrid is deliberate | High (two stacks) | When Snowflake + separate ML is mandated |

---

## 5. Recommendation & governance questions

**Recommendation (conditional):** Among **A–F** as defined here, **A — Databricks** **often** aligns best with a **Spark + Delta Lake + MLflow + job orchestration + SQL warehouse for BI** target — **provided** procurement and cloud strategy allow it. **Validate** against your actual contracts and security review.

| # | Question | If **yes** → consider |
|---|----------|------------------------|
| 1 | Need **Apache Spark** (e.g. MLlib or large PySpark ETL) at **very large** row counts with **fewer** first-party integrations to wire? | **A** or **Spark on EMR/Dataproc** (**B/C**) |
| 2 | Want **one vendor workspace** to chain ingest → prep → train → score with **managed** job scheduling? | **A** (Workflows) **or** equivalent orchestration on **B** (Step Functions, MWAA, etc.) — timeline depends on team |
| 3 | Need **Power BI** against large tables **without** Import-mode extracts? | **A** (Databricks SQL), **D**, or **E** — **confirm** connector and gateway for **your** tenant |
| 4 | Want **one** governance plane for **tables and registered models**? | **Unity Catalog** on **A** **or** assemble IAM/Lake Formation/registry patterns on **B** — compare effort |

---

## 6. Optional — requirement themes

Themes behind the comparison (from FMG internal architecture narrative): **scale**, **Delta-style medallion**, **incremental object-storage ingest**, **PySpark replacing SAS**, **MLlib + MLflow**, **batch scoring to curated tables**, **Power BI DirectQuery**, **orchestration**, **governance**, **ephemeral compute**. Under **those** assumptions, **A** is **typically** the closest **single-vendor** expression of the stack; **B/C** can match technically with **more** integration work; **E** shifts toward **warehouse-first** patterns; **F** splits responsibilities by design.

---

## Accuracy note (recheck)

| Topic | What we claim | What we do **not** claim |
|-------|----------------|---------------------------|
| Performance | Spark **can** scale to large row counts **when** tuned | Any fixed latency or “always faster than X” |
| Databricks | Integrated Spark + Delta + MLflow + jobs is **a** common selling point | Exclusive capability — Delta runs elsewhere too |
| Snowflake | Different execution model than multi-node **Apache Spark** for MLlib | That Snowflake cannot do ML (it can via Snowpark ML and partners) |
| AWS/GCP “assembled” | More moving parts **in typical** enterprise builds | That every AWS shop fails without Databricks |
| Weeks to DAG | **A** can shorten calendar time **in some** teams | Guaranteed delivery date |

---

---

*Audience: architecture / leadership · Revisit if cloud mandate, Snowflake standard, or “no Databricks” policy changes.*
