"""Elasticsearch and OpenSearch data directories; never modify cluster data."""

import stat

from whyfull.checks import check
from whyfull.model import INFO, Finding

MIN_BYTES = 5 * 10 ** 9
STORES = (("Elasticsearch", "/var/lib/elasticsearch", "ILM"),
          ("OpenSearch", "/var/lib/opensearch", "ISM"))


@check("search-data", "Elasticsearch and OpenSearch data")
def run(ctx):
    for product, path, retention in STORES:
        info = ctx.system.lstat(path)
        if info is None or not stat.S_ISDIR(info.st_mode) or not ctx.on_target(path):
            continue
        size = ctx.size(path)
        if size < MIN_BYTES:
            continue
        detail = ("Measured data size, not reclaimable space. Never delete files under this directory by hand. "
                  "Inspect indices through the cluster API and review retention, snapshots and application needs.")
        filesystem = ctx.filesystem(info.st_dev)
        if filesystem is not None and filesystem.percent >= 95:
            detail += (" Filesystem usage is at or above the default 95% flood-stage watermark; "
                       "indices may be read-only. "
                       "The configured watermark can differ, and cluster state has not been queried. "
                       "Recent versions release the block automatically after usage falls below the high watermark.")
        yield Finding(
            "search-data", path, "%s data in %s" % (product, path), size, INFO, info.st_dev,
            detail=detail,
            fix=[
                "# Use your cluster endpoint, HTTPS and authentication when security is enabled.",
                "curl -s 'http://localhost:9200/_cat/indices?v&s=store.size:desc'",
                "# Review backups and consumers before deleting old indices through the API or shrinking them.",
                "# Configure an %s retention policy to prevent recurring disk pressure." % retention,
            ],
            evidence=[path],
        )
