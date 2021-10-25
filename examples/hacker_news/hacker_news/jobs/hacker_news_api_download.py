import os
from datetime import datetime

from dagster import ResourceDefinition, graph, hourly_partitioned_config, in_process_executor
from dagster_pyspark import pyspark_resource
from hacker_news.ops.download_items import build_comments, build_stories, download_items
from hacker_news.ops.id_range_for_time import id_range_for_time
from hacker_news.resources import RESOURCES_LOCAL, RESOURCES_PROD, RESOURCES_STAGING
from hacker_news.resources.hn_resource import hn_api_subsample_client, hn_snapshot_client

# the configuration we'll need to make spark able to read from / write to s3
configured_pyspark = pyspark_resource.configured(
    {
        "spark_conf": {
            "spark.jars.packages": ",".join(
                [
                    "net.snowflake:snowflake-jdbc:3.8.0",
                    "net.snowflake:spark-snowflake_2.12:2.8.2-spark_3.0",
                    "com.amazonaws:aws-java-sdk:1.7.4,org.apache.hadoop:hadoop-aws:2.7.7",
                ]
            ),
            "spark.hadoop.fs.s3.impl": "org.apache.hadoop.fs.s3native.NativeS3FileSystem",
            "spark.hadoop.fs.s3.awsAccessKeyId": os.getenv("AWS_ACCESS_KEY_ID", ""),
            "spark.hadoop.fs.s3.awsSecretAccessKey": os.getenv("AWS_SECRET_ACCESS_KEY", ""),
            "spark.hadoop.fs.s3.buffer.dir": "/tmp",
        }
    }
)

DOWNLOAD_RESOURCES_LOCAL = dict(
    {
        "partition_start": ResourceDefinition.string_resource(),
        "partition_end": ResourceDefinition.string_resource(),
        "hn_client": hn_snapshot_client,
    },
    **RESOURCES_LOCAL,
)


DOWNLOAD_RESOURCES_STAGING = dict(
    **{
        "hn_client": hn_api_subsample_client.configured({"sample_rate": 10}),
        "partition_start": ResourceDefinition.string_resource(),
        "partition_end": ResourceDefinition.string_resource(),
    },
    **RESOURCES_STAGING,
)


DOWNLOAD_RESOURCES_PROD = dict(
    **{
        "hn_client": hn_api_subsample_client.configured({"sample_rate": 10}),
        "partition_start": ResourceDefinition.string_resource(),
        "partition_end": ResourceDefinition.string_resource(),
    },
    **RESOURCES_PROD,
)


DOWNLOAD_TAGS = {
    "dagster-k8s/config": {
        "container_config": {
            "resources": {
                "requests": {"cpu": "500m", "memory": "2Gi"},
            }
        },
    }
}


@graph
def hacker_news_api_download():
    """
    #### Owners
    schrockn@elementl.com, cat@elementl.com

    #### About
    Downloads all items from the HN API for a given day,
    splits the items into stories and comment types using Spark, and uploads filtered items to
    the corresponding stories or comments Snowflake table
    """
    items = download_items(id_range_for_time())
    build_comments(items)
    build_stories(items)


@hourly_partitioned_config(start_date=datetime(2020, 12, 1))
def hourly_download_config(start: datetime, end: datetime):
    return {
        "resources": {
            "partition_start": {"config": start.strftime("%Y-%m-%d %H:%M:%S")},
            "partition_end": {"config": end.strftime("%Y-%m-%d %H:%M:%S")},
        }
    }


download_prod_job = hacker_news_api_download.to_job(
    resource_defs=DOWNLOAD_RESOURCES_PROD,
    tags=DOWNLOAD_TAGS,
    config=hourly_download_config,
)


download_staging_job = hacker_news_api_download.to_job(
    resource_defs=DOWNLOAD_RESOURCES_STAGING,
    tags=DOWNLOAD_TAGS,
    config=hourly_download_config,
)

download_local_job = hacker_news_api_download.to_job(
    resource_defs=DOWNLOAD_RESOURCES_LOCAL,
    config={
        "resources": {
            "partition_start": {"config": "2020-12-30 00:00:00"},
            "partition_end": {"config": "2020-12-30 01:00:00"},
        }
    },
    executor_def=in_process_executor,
)
