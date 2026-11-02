"""Crash reports and core dumps."""

from whyfull.checks import check
from whyfull.model import REVIEW, Finding

MIN_BYTES = 100 * 10 ** 6

PLACES = [
    ("/var/lib/systemd/coredump", "systemd-coredump core dumps",
     ["sudo find /var/lib/systemd/coredump -type f -delete",
      "# cap them: set MaxUse=1G in /etc/systemd/coredump.conf"]),
    ("/var/crash", "crash reports in /var/crash", ["sudo find /var/crash -type f -delete"]),
    ("/var/lib/apport/coredump", "apport core dumps", ["sudo find /var/lib/apport/coredump -type f -delete"]),
    ("/var/spool/abrt", "ABRT crash reports", ["sudo abrt-cli remove /var/spool/abrt/*"]),
]


@check("crashes", "Core dumps and crash reports")
def run(ctx):
    for path, title, fix in PLACES:
        if not ctx.system.exists(path) or not ctx.on_target(path):
            continue
        size = ctx.size(path)
        if size < MIN_BYTES:
            continue
        yield Finding(
            "crashes", path, title, size, REVIEW, ctx.dev_of(path),
            detail=("Memory dumps from crashed programs. Useful for debugging a recent crash; "
                    "otherwise safe to delete."),
            fix=fix,
        )
