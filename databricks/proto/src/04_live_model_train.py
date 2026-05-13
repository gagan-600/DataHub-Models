# Databricks notebook source
# MAGIC %md
# MAGIC # 04 — Live model train (product-specific child model + MLflow)
# MAGIC
# MAGIC Trains only on rows where **`product_line`** matches the widget (transcript: sister / child model on product-specific samples). Uses **pandas** on the filtered slice (OK for fixture scale).

# COMMAND ----------

import mlflow
import mlflow.sklearn
import pandas as pd
from pyspark.sql import functions as F
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.model_selection import GroupShuffleSplit
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

try:
    _ohe = OneHotEncoder(handle_unknown="ignore", sparse_output=False)
except TypeError:
    _ohe = OneHotEncoder(handle_unknown="ignore", sparse=False)

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

pdf_all = spark.table(f"{catalog}.{silver_schema}.silver_sample_base").toPandas()
if "product_line" not in pdf_all.columns:
    raise ValueError("silver_sample_base missing product_line — re-run 01–03 after refreshing fixtures with product_line on SD.")
pdf = pdf_all[pdf_all["product_line"].astype(str).str.upper() == product_line].copy()
if len(pdf) < 50:
    raise ValueError(
        f"Too few training rows for product_line={product_line!r} (n={len(pdf)}). "
        "Pick another product_line or regenerate fixtures."
    )

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
cat_cols = ["stat_member_tier", "state", "campaign_channel", "offer_type"]
num_cols = [c for c in feature_cols if c not in cat_cols]

X = pdf[feature_cols].fillna(0)
y = pdf["response_flag"].astype(int)

preprocess = ColumnTransformer(
    [
        ("num", "passthrough", num_cols),
        ("cat", _ohe, cat_cols),
    ]
)
pipe = Pipeline(
    [
        ("prep", preprocess),
        ("clf", LogisticRegression(max_iter=300, class_weight="balanced", random_state=42)),
    ]
)

# COMMAND ----------

gss = GroupShuffleSplit(n_splits=1, test_size=0.25, random_state=42)
tr_idx, te_idx = next(gss.split(X, y, groups=pdf["customer_id"]))
X_train, X_test = X.iloc[tr_idx], X.iloc[te_idx]
y_train, y_test = y.iloc[tr_idx], y.iloc[te_idx]

try:
    mlflow.set_experiment("/Shared/marketing_proto_experiments")
except Exception:
    mlflow.set_experiment("marketing_proto_experiments")

trained_run_id = None
with mlflow.start_run(run_name=f"proto_lr_{product_line}_{run_tag}") as active:
    pipe.fit(X_train, y_train)
    prob = pipe.predict_proba(X_test)[:, 1]
    auc = float(roc_auc_score(y_test, prob))
    ap = float(average_precision_score(y_test, prob))
    mlflow.log_metric("auc_holdout", auc)
    mlflow.log_metric("avg_precision_holdout", ap)
    mlflow.log_param("train_rows", str(len(X_train)))
    mlflow.log_param("product_line", product_line)
    mlflow.sklearn.log_model(pipe, artifact_path="model")
    trained_run_id = active.info.run_id

# COMMAND ----------

meta = spark.createDataFrame(
    [
        (
            run_tag,
            trained_run_id,
            "sklearn_lr_product_specific",
            float(len(X_train)),
            product_line,
        )
    ],
    ["proto_run_id", "mlflow_run_id", "model_type", "train_row_ct", "product_line"],
).withColumn("trained_at", F.current_timestamp())
meta.write.format("delta").mode("append").option("mergeSchema", "true").saveAsTable(
    f"{catalog}.{gold_schema}.gold_proto_train_metadata"
)

print(f"product_line={product_line} MLflow run id={trained_run_id} auc={auc:.4f} ap={ap:.4f} train_rows={len(X_train)}")
