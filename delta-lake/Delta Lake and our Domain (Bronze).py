# Databricks notebook source
# MAGIC %md
# MAGIC # Delta Lake and our Domain (Bronze)
# MAGIC In this exercise, we'll do the following:
# MAGIC 1. Ingest from stream
# MAGIC 2. Write to Avro and store in a dedicated storage location, partitioned by year, month, day, hour, and minute
# MAGIC
# MAGIC ```
# MAGIC root
# MAGIC  |-- year=2023
# MAGIC  |    |-- month=1
# MAGIC  |    |    |-- day=1
# MAGIC  |    |    |    |-- hour=1
# MAGIC  |    |    |    |    |-- minute=1
# MAGIC  |    |    |    |    |-- minute=2
# MAGIC  |    |    |    |    |-- minute=3
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC ## Set up this Notebook
# MAGIC Before we get started, we need to quickly set up this notebook by installing a helpers, cleaning up your unique working directory (as to not clash with others working in the same space), and setting some variables. Run the following cells using shift + enter. **Note** that if your cluster shuts down, you will need to re-run the cells in this section.

# COMMAND ----------

# MAGIC %pip uninstall -y databricks_helpers databricks_helpers exercise_ev_production_code_delta_lake exercise_ev_databricks_unit_tests
# MAGIC %pip install git+https://github.com/data-derp/databricks_helpers#egg=databricks_helpers git+https://github.com/data-derp/exercise-ev-production-code-delta-lake#egg=exercise_ev_production_code_delta_lake git+https://github.com/data-derp/exercise_ev_databricks_unit_tests#egg=exercise_ev_databricks_unit_tests

# COMMAND ----------

exercise_name = "delta_lake_domain_bronze"

# COMMAND ----------

from databricks_helpers.databricks_helpers import DataDerpDatabricksHelpers

helpers = DataDerpDatabricksHelpers(dbutils, exercise_name)

current_user = helpers.current_user()
working_directory = helpers.working_directory()

print(f"Your current working directory is: {working_directory}")

# COMMAND ----------

## This function CLEARS your current working directory. Only run this if you want a fresh start or if it is the first time you're doing this exercise.
helpers.clean_working_directory()

# COMMAND ----------

# MAGIC %md
# MAGIC ## Read Data

# COMMAND ----------

from pyspark.sql import DataFrame
from pyspark.sql.types import StructType, StructField, StringType, IntegerType
import pandas as pd

def create_dataframe(url: str) -> DataFrame:
    pandas_df = pd.read_json(url, orient='records')
    pandas_df["index"] = pandas_df.index
    return spark.createDataFrame(pandas_df)

mock_data_df = create_dataframe("https://github.com/kelseymok/charge-point-simulator-v1.6/raw/main/out/1680355141.json.gz")
display(mock_data_df)

# COMMAND ----------

from pyspark.sql import DataFrame

def read_from_stream(input_df: DataFrame) -> DataFrame:
    raw_stream_data = (
        spark.readStream.format("rate")
        .option("rowsPerSecond", 10)
        .load()
    )

    # This is just data setup, not part of the exercise
    return raw_stream_data.\
        join(mock_data_df, raw_stream_data.value == mock_data_df.index, 'left').\
        drop("value").\
        drop("timestamp").\
        drop("index")

# COMMAND ----------

# MAGIC %md
# MAGIC ## EXERCISE: Set Partitioning Columns
# MAGIC In order to write to Avro in partitions (year, month, day, hour, and minute), we must extract the partitioning data from the existing DataFrame by using the [year](https://spark.apache.org/docs/3.1.1/api/python/reference/api/pyspark.sql.functions.year.html), [month](https://spark.apache.org/docs/3.1.1/api/python/reference/api/pyspark.sql.functions.month.html), [dayofmonth](https://spark.apache.org/docs/3.1.1/api/python/reference/api/pyspark.sql.functions.dayofmonth.html), [hour](https://spark.apache.org/docs/3.1.1/api/python/reference/api/pyspark.sql.functions.hour.html), and [minute](https://spark.apache.org/docs/3.1.1/api/python/reference/api/pyspark.sql.functions.minute.html) functions on the `write_timestamp` column to extract relevant metadata about the row.
# MAGIC
# MAGIC ```
# MAGIC root
# MAGIC  |-- message_id: string (nullable = true)
# MAGIC  |-- message_type: long (nullable = true)
# MAGIC  |-- charge_point_id: string (nullable = true)
# MAGIC  |-- action: string (nullable = true)
# MAGIC  |-- write_timestamp: string (nullable = true)
# MAGIC  |-- body: string (nullable = true)
# MAGIC  |-- write_timestamp_epoch: long (nullable = true)
# MAGIC  |-- year: integer (nullable = true)
# MAGIC  |-- month: integer (nullable = true)
# MAGIC  |-- day: integer (nullable = true)
# MAGIC  |-- hour: integer (nullable = true)
# MAGIC  |-- minute: integer (nullable = true)
# MAGIC  ```

# COMMAND ----------

from pyspark.sql import DataFrame
from pyspark.sql.functions import col, to_timestamp, year, month, dayofmonth, hour, minute, concat, lpad

def set_partitioning_cols(input_df: DataFrame):
    ### YOUR CODE HERE
    return input_df
    ###

set_partitioning_cols(read_from_stream(mock_data_df).transform(read_from_stream)).printSchema()

# COMMAND ----------

from exercise_ev_databricks_unit_tests.delta_lake_bronze import test_set_partitioning_cols_unit

test_set_partitioning_cols_unit(spark, set_partitioning_cols)

# COMMAND ----------

# MAGIC %md
# MAGIC ## EXERCISE: Write to Avro
# MAGIC Now that we've prepared our partitioning column, we now can write our stream to Avro by using [writeStream](https://spark.apache.org/docs/latest/api/python/reference/pyspark.sql/api/pyspark.sql.DataFrame.writeStream.html) and [partitionBy](https://spark.apache.org/docs/latest/api/python/reference/pyspark.sql/api/pyspark.sql.DataFrameWriter.partitionBy.html).

# COMMAND ----------

# Output directory
out_dir = f"{working_directory}/output/"
print(f"Output Directory: {out_dir}")

# Checkpoint directory
checkpoint_dir = f"{working_directory}/checkpoint/"
print(f"Checkpoint Directory: {out_dir}")

# COMMAND ----------

def write(input_df: DataFrame):
    ### YOUR CODE HERE
    partitioned_stream = input_df
    ###

    partitioned_stream.\
        option("checkpointLocation", checkpoint_dir).\
        option("path", out_dir).\
        format("avro").\
        start()

write(set_partitioning_cols(read_from_stream(mock_data_df).transform(read_from_stream)))

# COMMAND ----------

# MAGIC %md
# MAGIC After this has been running for a moment (the above streaming job keeps running), run the below command to see if there's any output in the expected directory. Notice that the data has been added to various labelled partitioning directories. Feel free to explore the directories!
# MAGIC
# MAGIC **Note:** If you get a "directory not found", just wait a moment and try again soon. 

# COMMAND ----------

display(spark.createDataFrame(dbutils.fs.ls(f"{out_dir}/year=2023/month=1/day=1/hour=9/minute=2")))

# COMMAND ----------

def test_files_exist(spark, **kwargs):
    result = spark.createDataFrame(dbutils.fs.ls(f"{kwargs['out_dir']}/year=2023/month=1/day=1/hour=9/minute=2"))
    result_count = result.count()
    expected_count = 2
    assert result_count == expected_count, f"expected {expected_count}, but got {result_count}"

    print("All tests pass! :)")

test_files_exist(spark, out_dir=out_dir)
