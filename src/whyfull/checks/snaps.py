"""Disabled snap revisions, which snapd keeps after every refresh."""

from whyfull.checks import check
from whyfull.model import SAFE, Finding

SNAPS = "/var/lib/snapd/snaps"
MIN_BYTES = 100 * 10 ** 6


def disabled_revisions(text):
    """Parse `snap list --all` and return (name, revision) of disabled revisions."""
    out = []
    lines = text.splitlines()
    for line in lines[1:]:
        cols = line.split()
        if len(cols) >= 4 and "disabled" in cols[-1].split(","):
            out.append((cols[0], cols[2]))
    return out


@check("snaps", "Disabled snap revisions")
def run(ctx):
    if not ctx.system.exists(SNAPS) or not ctx.on_target(SNAPS):
        return
    out = ctx.system.run(["snap", "list", "--all"])
    if not out:
        return
    items = []
    total = 0
    for name, rev in disabled_revisions(out):
        path = "%s/%s_%s.snap" % (SNAPS, name, rev)
        st = ctx.system.stat(path)
        size = st.st_blocks * 512 if st else 0
        total += size
        items.append((size, name, rev))
    if total < MIN_BYTES:
        return
    items.sort(reverse=True)
    yield Finding(
        "snaps", "disabled", "%d disabled snap revisions" % len(items), total, SAFE, ctx.dev_of(SNAPS),
        detail=("snapd keeps the previous revisions of every snap after an update so it can roll back. "
                "Removing disabled revisions is safe; limiting retention keeps them from piling up."),
        fix=["sudo snap remove %s --revision=%s" % (n, r) for _, n, r in items[:10]]
            + ["sudo snap set system refresh.retain=2"],
        evidence=["%s rev %s" % (n, r) for _, n, r in items[:10]],
    )
