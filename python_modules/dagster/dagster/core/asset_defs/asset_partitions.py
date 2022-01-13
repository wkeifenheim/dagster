from dagster import check
from dagster.core.definitions.events import AssetKey
from dagster.core.definitions.partition_key_range import PartitionKeyRange

from .asset import AssetsDefinition


def get_upstream_partitions_for_partition_range(
    downstream_assets_def: AssetsDefinition,
    upstream_assets_def: AssetsDefinition,
    upstream_asset_key: AssetKey,
    downstream_partition_key_range: PartitionKeyRange,
) -> PartitionKeyRange:
    """Returns the range of partition keys in the upstream asset that include data necessary
    to compute the contents of the given partition key range in the downstream asset.
    """

    if downstream_assets_def.partitions_def is None:
        check.failed("downstream asset is not partitioned")

    if upstream_assets_def.partitions_def is None:
        check.failed("upstream asset is not partitioned")

    downstream_partition_mapping = downstream_assets_def.get_partition_mapping(upstream_asset_key)
    return downstream_partition_mapping.get_upstream_partitions_for_partition_range(
        downstream_partition_key_range,
        downstream_assets_def.partitions_def,
        upstream_assets_def.partitions_def,
    )


def get_downstream_partitions_for_partition_range(
    downstream_assets_def: AssetsDefinition,
    upstream_assets_def: AssetsDefinition,
    upstream_asset_key: AssetKey,
    upstream_partition_key_range: PartitionKeyRange,
) -> PartitionKeyRange:
    """Returns the range of partition keys in the downstream asset that use the data in the given
    partition key range of the upstream asset.
    """
    if downstream_assets_def.partitions_def is None:
        check.failed("downstream asset is not partitioned")

    if upstream_assets_def.partitions_def is None:
        check.failed("upstream asset is not partitioned")

    downstream_partition_mapping = downstream_assets_def.get_partition_mapping(upstream_asset_key)
    return downstream_partition_mapping.get_downstream_partitions_for_partition_range(
        upstream_partition_key_range,
        downstream_assets_def.partitions_def,
        upstream_assets_def.partitions_def,
    )
