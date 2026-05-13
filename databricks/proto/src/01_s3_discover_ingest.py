# Databricks notebook source
# MAGIC %md
# MAGIC # 01 — Discover and ingest SD + STAT + responders (Spark → Delta)
# MAGIC
# MAGIC Reads Parquet from **`fixture_base`** (Unity Catalog **Volume** path recommended when DBFS is disabled on serverless).
# MAGIC **Do not** use long-lived AWS keys in widgets — use IAM roles / UC external locations.

# COMMAND ----------

from pyspark.sql import functions as F

REQUIRED_FIXTURE_FILES = (
    "sd_driver.parquet",
    "stat_promotion.parquet",
    "stat_membership.parquet",
    "stat_demographics.parquet",
    "responders.parquet",
)

dbutils.widgets.text("catalog", "workspace")
dbutils.widgets.text("bronze_schema", "marketing_proto_bronze")
dbutils.widgets.text("silver_schema", "marketing_proto_silver")
dbutils.widgets.text("gold_schema", "marketing_proto_gold")
dbutils.widgets.text("fixture_base", "/Volumes/workspace/default/marketing_proto_fixtures")
dbutils.widgets.text("run_id", "proto-run")

catalog = dbutils.widgets.get("catalog").strip()
bronze_schema = dbutils.widgets.get("bronze_schema").strip()
silver_schema = dbutils.widgets.get("silver_schema").strip()
gold_schema = dbutils.widgets.get("gold_schema").strip()
fixture_base = dbutils.widgets.get("fixture_base").strip().rstrip("/")
run_id = dbutils.widgets.get("run_id").strip()

for s in (bronze_schema, silver_schema, gold_schema):
    spark.sql(f"CREATE SCHEMA IF NOT EXISTS {catalog}.{s}")

base = fixture_base
try:
    found = {e.name for e in dbutils.fs.ls(base)}
except Exception as ex:
    raise RuntimeError(
        f"Cannot list fixture_base={base!r}. "
        "Create the UC Volume and upload Parquet files, or set widget fixture_base to a path your cluster can read. "
        f"Original error: {ex}"
    ) from ex
missing = [f for f in REQUIRED_FIXTURE_FILES if f not in found]
if missing:
    raise FileNotFoundError(
        f"Fixture data not found in {base}/. Missing files: {missing}. "
        "Upload the five Parquet files from the repo folder databricks/proto/fixtures/ into this Volume (or your chosen path)."
    )

# COMMAND ----------

sd_path = f"{base}/sd_driver.parquet"
stat_promo_path = f"{base}/stat_promotion.parquet"
stat_member_path = f"{base}/stat_membership.parquet"
stat_demo_path = f"{base}/stat_demographics.parquet"
resp_path = f"{base}/responders.parquet"

sd = spark.read.parquet(sd_path).withColumn("ingest_run_id", F.lit(run_id)).withColumn("ingest_ts", F.current_timestamp())
promo = spark.read.parquet(stat_promo_path).withColumn("ingest_run_id", F.lit(run_id)).withColumn("ingest_ts", F.current_timestamp())
member = spark.read.parquet(stat_member_path).withColumn("ingest_run_id", F.lit(run_id)).withColumn("ingest_ts", F.current_timestamp())
demo = spark.read.parquet(stat_demo_path).withColumn("ingest_run_id", F.lit(run_id)).withColumn("ingest_ts", F.current_timestamp())
resp = spark.read.parquet(resp_path).withColumn("ingest_run_id", F.lit(run_id)).withColumn("ingest_ts", F.current_timestamp())

sd.write.format("delta").mode("overwrite").option("overwriteSchema", "true").saveAsTable(f"{catalog}.{bronze_schema}.bronze_sd_driver")
promo.write.format("delta").mode("overwrite").option("overwriteSchema", "true").saveAsTable(f"{catalog}.{bronze_schema}.bronze_stat_promotion")
member.write.format("delta").mode("overwrite").option("overwriteSchema", "true").saveAsTable(f"{catalog}.{bronze_schema}.bronze_stat_membership")
demo.write.format("delta").mode("overwrite").option("overwriteSchema", "true").saveAsTable(f"{catalog}.{bronze_schema}.bronze_stat_demographics")
resp.write.format("delta").mode("overwrite").option("overwriteSchema", "true").saveAsTable(f"{catalog}.{bronze_schema}.bronze_responders")

print(f"OK: ingested from {base} into {catalog}.{bronze_schema}.*")
