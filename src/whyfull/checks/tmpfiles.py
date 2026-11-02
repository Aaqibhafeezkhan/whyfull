"""Old files in /tmp and /var/tmp."""

import os
import stat as statmod
import time

from whyfull.checks import check
from whyfull.model import REVIEW, Finding
from whyfull.units import human
from whyfull.walk import allocated

AGE_DAYS = 7
MIN_BYTES = 200 * 10 ** 6


@check("tmp", "Old files in /tmp and /var/tmp")
def run(ctx):
    cutoff = time.time() - AGE_DAYS * 86400
    for top in ("/tmp", "/var/tmp"):
        if not ctx.system.exists(top) or not ctx.on_target(top):
            continue
        dev = ctx.dev_of(top)
        total = 0
        biggest = []
        stack = [ctx.system.path(top)]
        while stack and not ctx.budget.expired():
            path = stack.pop()
            try:
                it = os.scandir(path)
            except OSError:
                continue
            with it:
                for entry in it:
                    try:
                        st = entry.stat(follow_symlinks=False)
                    except OSError:
                        continue
                    if st.st_dev != dev:
                        continue
                    if statmod.S_ISDIR(st.st_mode):
                        stack.append(entry.path)
                    elif statmod.S_ISREG(st.st_mode) and max(st.st_mtime, st.st_atime) < cutoff:
                        size = allocated(st)
                        total += size
                        biggest.append((size, ctx.system.display(entry.path)))
        if total < MIN_BYTES:
            continue
        biggest.sort(reverse=True)
        yield Finding(
            "tmp", top, "Files in %s untouched for %d+ days" % (top, AGE_DAYS), total, REVIEW, dev,
            detail=("Temporary files nothing has read or written in a week. Usually leftovers from "
                    "builds, downloads or crashed jobs; check the biggest ones before deleting."),
            fix=["sudo find %s -xdev -type f -mtime +%d -atime +%d -delete" % (top, AGE_DAYS, AGE_DAYS)],
            evidence=["%s  %s" % (human(s), p) for s, p in biggest[:5]],
        )
