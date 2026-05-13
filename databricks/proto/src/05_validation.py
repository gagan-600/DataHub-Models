# Databricks notebook source
# MAGIC %md
# MAGIC # 05 — Validation (product-specific: latest MLflow run for `product_line` + holdout on same slice)

import mlflow
import mlflow.sklearn
import pandas as pd
from pyspark.sql import functions as F
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.model_selection import GroupShuffleSplit

dbutils.widgets.text("catalog", "main")
dbutils.widgets.text("bronze_schema", "marketing_proto_bronze")
dbutils.widgets.text("silver_schema", "marketing_proto_silver")
dbutils.widgets.text("gold_schema", "marketing_proto_gold")
dbutils.widgets.text("fixture_base", "/dbfs/FileStore/marketing_proto_fixtures")
dbutils.widgets.text("run_id", "proto-run")
dbutils.widgets.text("product_line", "HOSPITAL_ACCIDENT")

catalog = dbutils.widgets.get("catalog").strip()
silver_schema = dbutils.widgets.get("silver_schema").strip()
gold_schema = dbutils.widgets.get("gold_schema").strip()
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

pdf_all = spark.table(f"{catalog}.{silver_schema}.silver_sample_base").toPandas()
pdf = pdf_all[pdf_all["product_line"].astype(str).str.upper() == product_line].copy()
if len(pdf) < 20:
    raise ValueError(f"Too few rows to validate for product_line={product_line!r} (n={len(pdf)}).")
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
X = pdf[feature_cols].fillna(0)
y = pdf["response_flag"].astype(int)

model = mlflow.sklearn.load_model(f"runs:/{mlflow_run_id}/model")

gss = GroupShuffleSplit(n_splits=1, test_size=0.25, random_state=42)
tr_idx, te_idx = next(gss.split(X, y, groups=pdf["customer_id"]))
X_test = X.iloc[te_idx]
y_test = y.iloc[te_idx]

prob = model.predict_proba(X_test)[:, 1]
auc = float(roc_auc_score(y_test, prob))
ap = float(average_precision_score(y_test, prob))

out = spark.createDataFrame(
    [(mlflow_run_id, product_line, auc, ap, int(len(te_idx)))],
    ["mlflow_run_id", "product_line", "auc_holdout", "avg_precision_holdout", "holdout_rows"],
)
out.write.format("delta").mode("overwrite").option("overwriteSchema", "true").saveAsTable(f"{catalog}.{gold_schema}.gold_validation_metrics")

print(f"Validation stored: product_line={product_line} auc={auc:.4f} ap={ap:.4f} holdout_rows={len(te_idx)}")
