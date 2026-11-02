"""Discover mounted filesystems and their usage."""

import os

from whyfull.model import Filesystem

# Filesystems that never hold user data, or are always "full" by design.
PSEUDO = {
    "proc", "sysfs", "devtmpfs", "devpts", "cgroup", "cgroup2", "pstore", "bpf",
    "securityfs", "debugfs", "tracefs", "configfs", "fusectl", "mqueue", "hugetlbfs",
    "binfmt_misc", "autofs", "efivarfs", "rpc_pipefs", "nsfs", "nfsd", "selinuxfs",
    "squashfs", "iso9660", "overlay", "ramfs", "fuse.lxcfs", "fuse.portal",
    "fuse.gvfsd-fuse", "fuse.snapfuse", "tmpfs",
}


def _unescape(s):
    # mountinfo escapes space, tab, newline and backslash as octal.
    return (s.replace("\\040", " ").replace("\\011", "\t")
            .replace("\\012", "\n").replace("\\134", "\\"))


def parse_mountinfo(text):
    """Yield (mountpoint, fstype, source) from /proc/self/mountinfo."""
    for line in text.splitlines():
        parts = line.split()
        if " - " not in line or len(parts) < 10:
            continue
        left, right = line.split(" - ", 1)
        lparts, rparts = left.split(), right.split()
        if len(lparts) < 5 or len(rparts) < 2:
            continue
        yield _unescape(lparts[4]), rparts[0], _unescape(rparts[1])


def usage(system, mountpoint, fstype, source):
    """Build a Filesystem from statvfs, or None if it can't be read."""
    try:
        st = system.statvfs(mountpoint)
    except OSError:
        return None
    dev_stat = system.stat(mountpoint)
    if dev_stat is None:
        return None
    frsize = st.f_frsize or st.f_bsize
    size = st.f_blocks * frsize
    if size == 0:
        return None
    used = (st.f_blocks - st.f_bfree) * frsize
    avail = st.f_bavail * frsize
    reserved = max(0, (st.f_bfree - st.f_bavail) * frsize)
    return Filesystem(
        mountpoint=mountpoint, source=source, fstype=fstype, dev=dev_stat.st_dev,
        size=size, used=used, avail=avail, inodes=st.f_files, inodes_free=st.f_ffree,
        reserved=reserved,
    )


def filesystems(system, include_pseudo=False):
    """Real filesystems, one per device (the shortest mountpoint wins)."""
    # system.proc is a local path (a fake /proc in tests), not a path to map.
    text = _read(os.path.join(system.proc, "self/mountinfo"))
    if text is None:
        return []
    by_dev = {}
    for mountpoint, fstype, source in parse_mountinfo(text):
        if not include_pseudo and fstype in PSEUDO:
            continue
        fs = usage(system, mountpoint, fstype, source)
        if fs is None:
            continue
        prev = by_dev.get(fs.dev)
        if prev is None or len(mountpoint) < len(prev.mountpoint):
            by_dev[fs.dev] = fs
    return sorted(by_dev.values(), key=lambda f: f.mountpoint)


def containing(system, path, candidates=None):
    """The filesystem holding path (including tmpfs and other pseudo filesystems)."""
    st = system.stat(path)
    if st is None:
        return None
    for fs in candidates or filesystems(system, include_pseudo=True):
        if fs.dev == st.st_dev:
            return fs
    return None


def _read(p):
    try:
        with open(p) as f:
            return f.read()
    except OSError:
        return None
