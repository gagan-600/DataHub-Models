# Databricks notebook source
# MAGIC %md
# MAGIC # 06 — Recommendations (stub)
# MAGIC
# MAGIC Replace with business rules / uplift / next-best-action when ready.

# COMMAND ----------

from pyspark.sql import functions as F

dbutils.widgets.text("catalog", "workspace")
dbutils.widgets.text("bronze_schema", "marketing_proto_bronze")
dbutils.widgets.text("silver_schema", "marketing_proto_silver")
dbutils.widgets.text("gold_schema", "marketing_proto_gold")
dbutils.widgets.text("fixture_base", "/Volumes/workspace/default/marketing_proto_fixtures")
dbutils.widgets.text("run_id", "proto-run")

catalog = dbutils.widgets.get("catalog").strip()
gold_schema = dbutils.widgets.get("gold_schema").strip()

stub = spark.createDataFrame(
    [("stub", "Replace with NBAs / uplift segments", 0.0)],
    ["recommendation_id", "note", "priority_score"],
)

# COMMAND ----------

stub.write.format("delta").mode("overwrite").option("overwriteSchema", "true").saveAsTable(f"{catalog}.{gold_schema}.gold_recommendations_stub")
print("OK: gold_recommendations_stub written")
