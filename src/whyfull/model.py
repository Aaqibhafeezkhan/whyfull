"""Data types shared by checks, the analyzer and the renderers."""

# Risk levels, from least to most care needed.
SAFE = "safe"  # caches and other data that is rebuilt or re-downloaded on demand
REVIEW = "review"  # logs, dumps, old files: usually fine to remove, but look first
CAUTION = "caution"  # has side effects: restarting a service, changing filesystem settings
INFO = "info"  # explains usage but frees nothing by itself

RISKS = (SAFE, REVIEW, CAUTION, INFO)


class Finding(object):
    """One explanation of where space went, with how to get it back.

    bytes  -- space that the fix frees (or explains, for INFO findings)
    dev    -- st_dev of the filesystem the space lives on; findings are only
              shown for the filesystem they belong to
    fix    -- shell commands, in order; may be empty for INFO findings
    """

    def __init__(self, check, key, title, nbytes, risk, dev,
                 detail="", fix=None, evidence=None, priority=0):
        if risk not in RISKS:
            raise ValueError("unknown risk %r" % (risk,))
        self.check = check
        self.key = key
        self.title = title
        self.bytes = int(nbytes or 0)
        self.risk = risk
        self.dev = dev
        self.detail = detail
        self.fix = list(fix or [])
        self.evidence = list(evidence or [])
        # Higher priority findings are shown first regardless of size
        # (e.g. inode exhaustion, which no amount of byte-freeing fixes).
        self.priority = priority

    @property
    def id(self):
        return "%s:%s" % (self.check, self.key)

    def to_dict(self):
        return {
            "id": self.id,
            "check": self.check,
            "title": self.title,
            "bytes": self.bytes,
            "risk": self.risk,
            "detail": self.detail,
            "fix": self.fix,
            "evidence": self.evidence,
        }

    def __repr__(self):  # pragma: no cover - debugging aid
        return "Finding(%s, %d bytes, %s)" % (self.id, self.bytes, self.risk)


class Filesystem(object):
    """A mounted filesystem and its usage, as df would show it."""

    def __init__(self, mountpoint, source, fstype, dev, size, used, avail,
                 inodes=0, inodes_free=0, reserved=0):
        self.mountpoint = mountpoint
        self.source = source
        self.fstype = fstype
        self.dev = dev
        self.size = size
        self.used = used
        self.avail = avail
        self.inodes = inodes
        self.inodes_free = inodes_free
        self.reserved = reserved

    @property
    def percent(self):
        """Use% the way df computes it: used / (used + avail), rounded up."""
        denom = self.used + self.avail
        if denom <= 0:
            return 0
        return -(-int(self.used) * 100 // int(denom))  # ceiling division, like df

    @property
    def inode_percent(self):
        if not self.inodes:
            return 0.0
        used = self.inodes - self.inodes_free
        return 100.0 * used / self.inodes

    def to_dict(self):
        return {
            "mountpoint": self.mountpoint,
            "source": self.source,
            "fstype": self.fstype,
            "size": self.size,
            "used": self.used,
            "avail": self.avail,
            "percent": self.percent,
            "inodes": self.inodes,
            "inodes_free": self.inodes_free,
            "inode_percent": round(self.inode_percent, 1),
            "reserved": self.reserved,
        }
