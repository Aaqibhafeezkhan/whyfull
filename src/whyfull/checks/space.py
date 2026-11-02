"""Filesystem-level causes: inode exhaustion and root-reserved blocks."""

from whyfull.checks import check
from whyfull.model import CAUTION, INFO, Finding
from whyfull.units import human

INODE_WARN = 90.0


@check("inodes", "Out of inodes (too many files, not too many bytes)")
def inodes(ctx):
    for fs in ctx.targets:
        if not fs.inodes or fs.inode_percent < INODE_WARN:
            continue
        used = fs.inodes - fs.inodes_free
        yield Finding(
            "inodes", fs.mountpoint,
            "%s is out of inodes: %.0f%% used (%s of %s files)" % (
                fs.mountpoint, fs.inode_percent, "{:,}".format(used), "{:,}".format(fs.inodes)),
            0, INFO, fs.dev, priority=100,
            detail=("Every file needs an inode, and this filesystem has almost none left, so "
                    "new files fail with 'No space left on device' even though bytes are free. "
                    "The fix is deleting files, usually millions of tiny ones in one directory. "
                    "The directories with the most entries are listed under 'Crowded directories'."),
            fix=["sudo find %s -xdev -type d -size +1M  # directories with very many entries" % fs.mountpoint],
        )


@check("reserved", "Blocks reserved for root")
def reserved(ctx):
    for fs in ctx.targets:
        if fs.reserved <= 0 or not fs.fstype.startswith("ext"):
            continue
        # Only worth raising when the reserve is what makes the disk look full.
        if fs.avail > fs.reserved or fs.reserved < 0.01 * fs.size:
            continue
        system_disk = fs.mountpoint in ("/", "/boot", "/var", "/usr")
        detail = ("ext filesystems keep about 5%% of their blocks for root, so services running as "
                  "other users get 'No space left on device' while %s is still free for root. " % human(fs.reserved))
        if system_disk:
            detail += "Keep this reserve on a system disk: it lets root log in and clean up."
            risk, fix = INFO, []
        else:
            detail += "On a data-only disk, lowering the reserve to 1% is common."
            risk, fix = CAUTION, ["sudo tune2fs -m 1 %s" % fs.source]
        yield Finding(
            "reserved", fs.mountpoint,
            "%s still free on %s is reserved for root" % (human(fs.reserved), fs.mountpoint),
            fs.reserved if risk == CAUTION else 0, risk, fs.dev, detail=detail, fix=fix,
        )
