"""The systemd journal."""

from whyfull.checks import check
from whyfull.model import REVIEW, Finding
from whyfull.units import human

KEEP = 200 * 10 ** 6  # what we suggest vacuuming down to
MIN_RECLAIM = 100 * 10 ** 6


@check("journald", "systemd journal")
def run(ctx):
    for path in ("/var/log/journal", "/run/log/journal"):
        if not ctx.system.exists(path) or not ctx.on_target(path):
            continue
        size = ctx.size(path)
        reclaim = size - KEEP
        if reclaim < MIN_RECLAIM:
            continue
        yield Finding(
            "journald", path, "systemd journal in %s is %s" % (path, human(size)),
            reclaim, REVIEW, ctx.dev_of(path),
            detail=("journald keeps old logs until it reaches its size cap (by default 10%% of "
                    "the filesystem). Vacuuming keeps the newest %s; capping it stops it "
                    "growing back." % human(KEEP)),
            fix=[
                "sudo journalctl --vacuum-size=200M",
                "# keep it capped:",
                "sudo mkdir -p /etc/systemd/journald.conf.d",
                "printf '[Journal]\\nSystemMaxUse=200M\\n' | sudo tee /etc/systemd/journald.conf.d/size.conf",
                "sudo systemctl restart systemd-journald",
            ],
        )
