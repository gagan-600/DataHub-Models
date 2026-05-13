# Databricks notebook source
# MAGIC %md
# MAGIC # 03 — Auto sample prep (MRGAL + responders append + optional flags)

from pyspark.sql import functions as F

dbutils.widgets.text("catalog", "main")
dbutils.widgets.text("bronze_schema", "marketing_proto_bronze")
dbutils.widgets.text("silver_schema", "marketing_proto_silver")
dbutils.widgets.text("gold_schema", "marketing_proto_gold")
dbutils.widgets.text("fixture_base", "/dbfs/FileStore/marketing_proto_fixtures")
dbutils.widgets.text("run_id", "proto-run")

catalog = dbutils.widgets.get("catalog").strip()
bronze_schema = dbutils.widgets.get("bronze_schema").strip()
silver_schema = dbutils.widgets.get("silver_schema").strip()
run_id = dbutils.widgets.get("run_id").strip()

mrgal = spark.table(f"{catalog}.{silver_schema}.silver_mrgal_universe")
resp = spark.table(f"{catalog}.{bronze_schema}.bronze_responders").select(
    "pit_key",
    F.col("responded_at").alias("resp_responded_at"),
    F.col("response_channel").alias("resp_response_channel"),
)

sample = (
    mrgal.join(resp, on="pit_key", how="left")
    .withColumn("responder_joined", F.when(F.col("resp_responded_at").isNotNull(), F.lit(1)).otherwise(F.lit(0)))
    .withColumn("sample_prep_run_id", F.lit(run_id))
    .withColumn("sample_prep_ts", F.current_timestamp())
)

sample.write.format("delta").mode("overwrite").option("overwriteSchema", "true").saveAsTable(f"{catalog}.{silver_schema}.silver_sample_base")

joined = sample.filter(F.col("responder_joined") == 1).count()
print(f"sample_base rows={sample.count()} responder_joined={joined}")
