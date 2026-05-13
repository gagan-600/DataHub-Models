# Databricks notebook source
# MAGIC %md
# MAGIC # 07 — Batch score (product-specific model: scores rows where `product_line` matches widget; others get null `prediction_prob`)

# COMMAND ----------

import mlflow
import mlflow.sklearn
import numpy as np
import pandas as pd
from pyspark.sql import functions as F

dbutils.widgets.text("catalog", "workspace")
dbutils.widgets.text("bronze_schema", "marketing_proto_bronze")
dbutils.widgets.text("silver_schema", "marketing_proto_silver")
dbutils.widgets.text("gold_schema", "marketing_proto_gold")
dbutils.widgets.text("fixture_base", "/Volumes/workspace/default/marketing_proto_fixtures")
dbutils.widgets.text("run_id", "proto-run")
dbutils.widgets.text("product_line", "HOSPITAL_ACCIDENT")

catalog = dbutils.widgets.get("catalog").strip()
silver_schema = dbutils.widgets.get("silver_schema").strip()
gold_schema = dbutils.widgets.get("gold_schema").strip()
run_tag = dbutils.widgets.get("run_id").strip()
product_line = dbutils.widgets.get("product_line").strip().upper()

meta_df = spark.table(f"{catalog}.{gold_schema}.gold_proto_train_metadata").filter(
    F.upper(F.col("product_line")) == F.lit(product_line)
)
meta_rows = meta_df.orderBy(F.desc("trained_at")).limit(1).collect()
if not meta_rows:
    raise ValueError(
        f"No train metadata for product_line={product_line!r}. Run 04 with the same product_line first."
    )
meta_row = meta_rows[0]
mlflow_run_id = meta_row.mlflow_run_id

model = mlflow.sklearn.load_model(f"runs:/{mlflow_run_id}/model")

# COMMAND ----------

pdf = spark.table(f"{catalog}.{silver_schema}.silver_sample_base").toPandas()
if "product_line" not in pdf.columns:
    raise ValueError("silver_sample_base missing product_line — re-run 01–03 after refreshing fixtures.")
feature_cols = [
    "income",
    "monthly_premium",
    "months_since_last_claim",
    "clv",
    "stat_promo_touch_count_90d",
    "stat_tenure_months",
    "stat_active_products_ct",
    "stat_member_tier",
    "state",
    "campaign_channel",
    "offer_type",
]
mask = pdf["product_line"].astype(str).str.upper() == product_line
X = pdf[feature_cols].fillna(0)
pdf["prediction_prob"] = np.nan
pdf.loc[mask, "prediction_prob"] = model.predict_proba(X.loc[mask])[:, 1]
pdf["score_run_id"] = run_tag
pdf["mlflow_run_id"] = mlflow_run_id
pdf["model_product_line"] = product_line

# COMMAND ----------

keep = [
    "pit_key",
    "customer_id",
    "campaign_id",
    "product_line",
    "response_flag",
    "responder_joined",
    "prediction_prob",
    "model_product_line",
    "score_run_id",
    "mlflow_run_id",
]
scored = spark.createDataFrame(pdf[keep])

scored.write.format("delta").mode("overwrite").option("overwriteSchema", "true").saveAsTable(f"{catalog}.{gold_schema}.gold_scored")

print(f"OK: gold_scored rows={scored.count()} product_line={product_line} runs:/{mlflow_run_id}/model")
