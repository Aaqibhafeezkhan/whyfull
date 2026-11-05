"""PostgreSQL write-ahead logs retained by replication or archiving."""

import stat

from whyfull.checks import check
from whyfull.model import INFO, Finding

MIN_BYTES = 2 * 10 ** 9


def data_directories(system):
    for version in system.listdir("/var/lib/postgresql"):
        yield "/var/lib/postgresql/" + version + "/main"
    yield "/var/lib/pgsql/data"
    for version in system.listdir("/var/lib/pgsql"):
        if version != "data":
            yield "/var/lib/pgsql/" + version + "/data"


@check("postgresql", "PostgreSQL write-ahead logs")
def run(ctx):
    for directory in data_directories(ctx.system):
        for name in ("pg_wal", "pg_xlog"):
            path = directory + "/" + name
            info = ctx.system.lstat(path)
            if info is None or not stat.S_ISDIR(info.st_mode) or not ctx.on_target(path):
                continue
            size = ctx.size(path)
            if size < MIN_BYTES:
                continue
            yield Finding(
                "postgresql", path, "PostgreSQL write-ahead logs in %s" % path,
                size, INFO, ctx.dev_of(path),
                detail=("Large WAL usage can be caused by inactive replication slots or failing archiving. "
                        "This is allocated space, not an estimate of reclaimable bytes. Never delete WAL by hand."),
                fix=[
                    'sudo -u postgres psql -c "SELECT slot_name, active FROM pg_replication_slots;"',
                    'sudo -u postgres psql -c "SELECT * FROM pg_stat_archiver;"',
                    "# Connect to the affected cluster; these commands use the default local connection.",
                    "# Only drop a replication slot after confirming no replica or consumer needs it.",
                    "# PostgreSQL can recycle retained WAL after the slot or archiving problem is resolved.",
                ],
            )
