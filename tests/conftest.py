import os
import sys
import time
import types

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from whyfull.checks import Context  # noqa: E402
from whyfull.model import Filesystem  # noqa: E402
from whyfull.system import System  # noqa: E402
from whyfull.walk import Budget  # noqa: E402

GB = 2 ** 30  # keeps fake sizes whole multiples of the 4 KiB block size

FAKE_DEV_BASE = 10 ** 9


class _Stat(object):
    """A stat result with a different st_dev."""

    def __init__(self, real, dev):
        self._real = real
        self.st_dev = dev

    def __getattr__(self, name):
        return getattr(self._real, name)


class FakeSystem(System):
    """Every extra fake mount lives on the same real disk, so give each its own st_dev."""

    def __init__(self, devs, **kw):
        System.__init__(self, **kw)
        self._devs = devs  # [(mountpoint, fake dev)], longest first

    def _fix(self, p, st):
        if st is None:
            return None
        for mp, dev in self._devs:
            if p == mp or p.startswith(mp + "/"):
                return _Stat(st, dev)
        return st

    def stat(self, p):
        return self._fix(p, System.stat(self, p))

    def lstat(self, p):
        return self._fix(p, System.lstat(self, p))


class FakeRoot(object):
    """A directory that plays the part of / for one test."""

    def __init__(self, path):
        self.path = str(path)
        self.proc = os.path.join(self.path, "proc")
        os.makedirs(os.path.join(self.proc, "self"))
        os.makedirs(os.path.join(self.proc, "sys", "kernel"))
        self.commands = {}
        self.mounts = [("/", "ext4", "/dev/sda1")]
        self.stats = {}  # mountpoint -> dict of statvfs fields
        self.kernel("6.8.0-45-generic")
        self.write("/etc/os-release", 'ID=ubuntu\nID_LIKE=debian\n')
        self.write("/etc/passwd", "root:x:0:0:root:/root:/bin/bash\n"
                                  "alice:x:1000:1000::/home/alice:/bin/bash\n"
                                  "daemon:x:2:2::/usr/sbin:/usr/sbin/nologin\n")

    def local(self, p):
        return os.path.join(self.path, p.lstrip("/"))

    def write(self, p, content="", size=None, age_days=0):
        full = self.local(p)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "wb") as f:
            f.write(content.encode() if isinstance(content, str) else content)
            if size:
                f.write(os.urandom(size))
        if age_days:
            t = time.time() - age_days * 86400
            os.utime(full, (t, t))
        return full

    def mkdir(self, p):
        os.makedirs(self.local(p), exist_ok=True)

    def kernel(self, release):
        with open(os.path.join(self.proc, "sys", "kernel", "osrelease"), "w") as f:
            f.write(release + "\n")

    def set_usage(self, mountpoint="/", size=100 * GB, used=90 * GB, avail=None,
                  inodes=1000000, inodes_free=500000, reserved=0):
        bs = 4096
        avail = size - used - reserved if avail is None else avail
        self.stats[mountpoint] = dict(
            f_bsize=bs, f_frsize=bs, f_blocks=size // bs, f_bfree=(size - used) // bs,
            f_bavail=avail // bs, f_files=inodes, f_ffree=inodes_free, f_favail=inodes_free,
            f_flag=0, f_namemax=255,
        )

    def statvfs(self, local_path):
        display = "/" + os.path.relpath(local_path, self.path).lstrip(".").lstrip("/")
        fields = self.stats.get(display.rstrip("/") or "/") or self.stats.get("/")
        if fields is None:
            raise OSError("no fake usage for %s" % display)
        return types.SimpleNamespace(**fields)

    def runner(self, argv):
        if argv[0] == "which":
            return "/usr/bin/" + argv[1] if any(k[0] == argv[1] for k in self.commands) else None
        return self.commands.get(tuple(argv))

    def system(self, euid=0):
        with open(os.path.join(self.proc, "self", "mountinfo"), "w") as f:
            for i, (mp, fstype, src) in enumerate(self.mounts):
                self.mkdir(mp)
                f.write("%d 1 8:%d / %s rw - %s %s rw\n" % (20 + i, i, mp, fstype, src))
        if not self.stats:
            self.set_usage()
        devs = sorted(((mp, FAKE_DEV_BASE + i) for i, (mp, _, _) in enumerate(self.mounts) if mp != "/"),
                      key=lambda md: -len(md[0]))
        return FakeSystem(devs, root=self.path, proc=self.proc, runner=self.runner, euid=euid,
                          statvfs=self.statvfs)


@pytest.fixture
def root(tmp_path):
    return FakeRoot(tmp_path / "root")


def make_ctx(system, mountpoint="/", fstype="ext4", seconds=30):
    st = system.stat(mountpoint)
    fs = Filesystem(mountpoint=mountpoint, source="/dev/sda1", fstype=fstype, dev=st.st_dev,
                    size=100 * GB, used=90 * GB, avail=10 * GB)
    return Context(system, [fs], Budget(seconds))
