# Databricks notebook source
# MAGIC %md
# MAGIC # 02 — Auto MRGAL (join SD + all STAT feeds on `pit_key`)

# COMMAND ----------

from pyspark.sql import functions as F

dbutils.widgets.text("catalog", "workspace")
dbutils.widgets.text("bronze_schema", "marketing_proto_bronze")
dbutils.widgets.text("silver_schema", "marketing_proto_silver")
dbutils.widgets.text("gold_schema", "marketing_proto_gold")
dbutils.widgets.text("fixture_base", "/Volumes/workspace/default/marketing_proto_fixtures")
dbutils.widgets.text("run_id", "proto-run")

catalog = dbutils.widgets.get("catalog").strip()
bronze_schema = dbutils.widgets.get("bronze_schema").strip()
silver_schema = dbutils.widgets.get("silver_schema").strip()
run_id = dbutils.widgets.get("run_id").strip()

sd = spark.table(f"{catalog}.{bronze_schema}.bronze_sd_driver")
promo = spark.table(f"{catalog}.{bronze_schema}.bronze_stat_promotion")
member = spark.table(f"{catalog}.{bronze_schema}.bronze_stat_membership")
demo = spark.table(f"{catalog}.{bronze_schema}.bronze_stat_demographics")

# Rename overlapping non-key columns before join (if any)
promo_c = promo.select(
    "pit_key",
    F.col("promo_touch_count_90d").alias("stat_promo_touch_count_90d"),
    F.col("last_promo_channel").alias("stat_last_promo_channel"),
    F.col("promo_spend_band").alias("stat_promo_spend_band"),
    "ingest_run_id",
    "ingest_ts",
)
member_c = member.select(
    "pit_key",
    F.col("member_tier").alias("stat_member_tier"),
    F.col("tenure_months").alias("stat_tenure_months"),
    F.col("active_products_ct").alias("stat_active_products_ct"),
    "ingest_run_id",
    "ingest_ts",
)
demo_c = demo.select(
    "pit_key",
    F.col("demo_region_bucket").alias("stat_demo_region_bucket"),
    F.col("income_band").alias("stat_income_band"),
    "ingest_run_id",
    "ingest_ts",
)

mrgal = (
    sd.drop("ingest_run_id", "ingest_ts")
    .join(promo_c.drop("ingest_run_id", "ingest_ts"), on="pit_key", how="left")
    .join(member_c.drop("ingest_run_id", "ingest_ts"), on="pit_key", how="left")
    .join(demo_c.drop("ingest_run_id", "ingest_ts"), on="pit_key", how="left")
    .withColumn("mrgal_run_id", F.lit(run_id))
    .withColumn("mrgal_built_ts", F.current_timestamp())
)

# COMMAND ----------

mrgal.write.format("delta").mode("overwrite").option("overwriteSchema", "true").saveAsTable(f"{catalog}.{silver_schema}.silver_mrgal_universe")

cnt_sd = sd.count()
cnt_out = mrgal.count()
print(f"MRGAL rows={cnt_out} (SD rows={cnt_sd})")
