"""Access to the machine being inspected.

Everything that touches the real system goes through System, so tests can
point it at a fake root directory, a fake /proc and canned command output.
"""

import os
import pwd
import shutil
import subprocess


class System(object):
    def __init__(self, root="/", proc=None, runner=None, kernel_release=None,
                 euid=None, statvfs=None, passwd=None):
        self.root = os.path.abspath(root)
        if proc is None:
            proc = "/proc" if self.root == "/" else os.path.join(self.root, "proc")
        self.proc = proc
        self._runner = runner
        self._kernel_release = kernel_release
        self._euid = euid
        self._statvfs = statvfs or os.statvfs
        self._passwd = passwd

    # ---- paths ---------------------------------------------------------

    def path(self, p):
        """Map an absolute path on the inspected system to a local path."""
        if self.root == "/":
            return p
        return os.path.join(self.root, p.lstrip("/"))

    def display(self, local):
        """Map a local path back to the path as seen on the inspected system."""
        if self.root == "/":
            return local
        rel = os.path.relpath(local, self.root)
        return "/" if rel == "." else "/" + rel

    def exists(self, p):
        return os.path.lexists(self.path(p))

    def read_text(self, p, default=None):
        try:
            with open(self.path(p), "r") as f:
                return f.read()
        except (OSError, UnicodeDecodeError):
            return default

    def listdir(self, p):
        try:
            return sorted(os.listdir(self.path(p)))
        except OSError:
            return []

    def stat(self, p):
        try:
            return os.stat(self.path(p))
        except OSError:
            return None

    def lstat(self, p):
        try:
            return os.lstat(self.path(p))
        except OSError:
            return None

    def statvfs(self, p):
        return self._statvfs(self.path(p))

    # ---- identity ------------------------------------------------------

    @property
    def euid(self):
        return os.geteuid() if self._euid is None else self._euid

    @property
    def is_root(self):
        return self.euid == 0

    def kernel_release(self):
        if self._kernel_release is not None:
            return self._kernel_release
        try:
            with open(os.path.join(self.proc, "sys/kernel/osrelease")) as f:
                return f.read().strip()
        except OSError:
            return os.uname()[2]

    def os_release(self):
        """Fields of /etc/os-release as a dict (ID, ID_LIKE, ...)."""
        text = self.read_text("/etc/os-release") or self.read_text("/usr/lib/os-release") or ""
        out = {}
        for line in text.splitlines():
            if "=" not in line or line.startswith("#"):
                continue
            k, v = line.split("=", 1)
            out[k.strip()] = v.strip().strip('"').strip("'")
        return out

    def distro_family(self):
        info = self.os_release()
        ids = (info.get("ID", "") + " " + info.get("ID_LIKE", "")).lower().split()
        for family in ("debian", "ubuntu", "rhel", "fedora", "centos", "suse", "arch", "alpine"):
            if family in ids:
                return {"ubuntu": "debian", "centos": "rhel", "fedora": "rhel"}.get(family, family)
        return ""

    def users(self):
        """(name, home) for root and regular users whose home directory exists."""
        entries = self._passwd
        if entries is None:
            try:
                entries = [(p.pw_name, p.pw_uid, p.pw_dir) for p in pwd.getpwall()] \
                    if self.root == "/" else self._passwd_file()
            except Exception:
                entries = []
        seen = set()
        out = []
        for name, uid, home in entries:
            if not home or home in seen or home in ("/", "/nonexistent"):
                continue
            if uid != 0 and uid < 1000:
                continue
            if not os.path.isdir(self.path(home)):
                continue
            seen.add(home)
            out.append((name, home))
        return out

    def _passwd_file(self):
        out = []
        for line in (self.read_text("/etc/passwd") or "").splitlines():
            parts = line.split(":")
            if len(parts) >= 6:
                try:
                    out.append((parts[0], int(parts[2]), parts[5]))
                except ValueError:
                    continue
        return out

    # ---- commands ------------------------------------------------------

    def has(self, binary):
        if self._runner is not None:
            return self._runner(["which", binary]) is not None
        return shutil.which(binary) is not None

    def run(self, argv, timeout=30):
        """Run a read-only command. Returns stdout, or None if it is missing or fails."""
        if self._runner is not None:
            return self._runner(list(argv))
        if shutil.which(argv[0]) is None:
            return None
        try:
            proc = subprocess.run(
                argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                stdin=subprocess.DEVNULL, timeout=timeout, universal_newlines=True,
                env=dict(os.environ, LC_ALL="C"),
            )
        except (OSError, subprocess.SubprocessError):
            return None
        if proc.returncode != 0:
            return None
        return proc.stdout
