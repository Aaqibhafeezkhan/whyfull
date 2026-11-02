"""Files that were deleted while a process still had them open.

The classic "df says full, du says empty" problem: deleting a log file that a
service is writing to removes its name, but the space is only released when
the last process closes it.
"""

import os
import re

from whyfull.checks import check
from whyfull.model import CAUTION, Finding
from whyfull.walk import allocated

MIN_BYTES = 1 << 20  # ignore groups smaller than 1 MiB

_UNIT_RE = re.compile(r"/([^/]+\.service)(?:/|$)")
_DOCKER_RE = re.compile(r"docker[-/]([0-9a-f]{12,64})")


def _read(path):
    try:
        with open(path) as f:
            return f.read()
    except OSError:
        return ""


def owner_of(proc, pid):
    """('unit', 'nginx.service') / ('container', 'abc123...') / ('process', 'name')."""
    cgroup = _read(os.path.join(proc, pid, "cgroup"))
    m = _DOCKER_RE.search(cgroup)
    if m:
        return "container", m.group(1)[:12]
    units = _UNIT_RE.findall(cgroup)
    # Skip per-user manager units; user@1000.service is not what holds the file.
    units = [u for u in units if not u.startswith("user@")]
    if units:
        return "unit", units[-1]
    comm = _read(os.path.join(proc, pid, "comm")).strip() or "pid " + pid
    return "process", comm


def scan_proc(proc):
    """Yield (pid, fd, target, stat) for every open file that has been deleted."""
    try:
        pids = [p for p in os.listdir(proc) if p.isdigit()]
    except OSError:
        return
    for pid in pids:
        fd_dir = os.path.join(proc, pid, "fd")
        try:
            fds = os.listdir(fd_dir)
        except OSError:
            continue
        for fd in fds:
            fd_path = os.path.join(fd_dir, fd)
            try:
                target = os.readlink(fd_path)
            except OSError:
                continue
            if not target.endswith(" (deleted)") or not target.startswith("/"):
                continue
            if target.startswith("/memfd:"):
                continue
            try:
                st = os.stat(fd_path)
            except OSError:
                continue
            if st.st_nlink != 0:
                continue
            yield pid, fd, target[: -len(" (deleted)")], st


@check("deleted-open", "Deleted files still held open by a process")
def run(ctx):
    groups = {}  # (dev, kind, name) -> dict
    seen = set()
    for pid, fd, path, st in scan_proc(ctx.system.proc):
        if st.st_dev not in ctx.target_devs:
            continue
        kind, name = owner_of(ctx.system.proc, pid)
        g = groups.setdefault((st.st_dev, kind, name), {"bytes": 0, "files": {}, "fds": []})
        g["fds"].append((pid, fd))
        key = (st.st_dev, st.st_ino)
        if key in seen:
            continue
        seen.add(key)
        size = allocated(st)
        g["bytes"] += size
        g["files"][path] = g["files"].get(path, 0) + size

    if not ctx.system.is_root:
        ctx.note("Run with sudo to see deleted files held open by other users' processes.")

    for (dev, kind, name), g in groups.items():
        ctx.deleted_open_bytes[dev] = ctx.deleted_open_bytes.get(dev, 0) + g["bytes"]
        if g["bytes"] < MIN_BYTES:
            continue
        nfiles = len(g["files"])
        noun = "file" if nfiles == 1 else "files"
        if kind == "unit":
            short = name[: -len(".service")]
            title = "%d deleted %s still open by %s" % (nfiles, noun, name)
            fix = ["sudo systemctl restart %s" % short]
        elif kind == "container":
            title = "%d deleted %s still open in container %s" % (nfiles, noun, name)
            fix = ["docker restart %s" % name]
        else:
            title = "%d deleted %s still open by %s" % (nfiles, noun, name)
            fix = ["# restart %s, or free the space without a restart:" % name]
        # Truncating through /proc frees the space immediately and keeps the process running.
        truncate = ["sudo truncate -s 0 /proc/%s/fd/%s" % (p, f) for p, f in sorted(set(g["fds"]))[:5]]
        if kind != "process":
            fix.append("# or free the space without a restart:")
        fix.extend(truncate)
        biggest = sorted(g["files"].items(), key=lambda kv: -kv[1])[:5]
        evidence = ["%s (deleted)" % (ctx.system.display(p) if p.startswith(ctx.system.root + "/") else p)
                    for p, _ in biggest]
        yield Finding(
            "deleted-open", "%s:%s" % (kind, name), title, g["bytes"], CAUTION, dev,
            detail=("These files were deleted, but the process writing to them never closed "
                    "them, so the space is still in use. du can't see it; df can."),
            fix=fix, evidence=evidence,
        )
