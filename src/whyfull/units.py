"""Human-readable sizes, in both directions."""

import re

_UNITS = ["B", "KB", "MB", "GB", "TB", "PB"]


def human(n):
    """Format a byte count the way df -h --si does, e.g. 14.2 GB."""
    if n is None:
        return "?"
    n = float(n)
    for unit in _UNITS:
        if abs(n) < 1000 or unit == _UNITS[-1]:
            if unit == "B":
                return "{} B".format(int(n))
            if abs(n) >= 99.95:
                return "{:.0f} {}".format(n, unit)
            return "{:.1f} {}".format(n, unit)
        n /= 1000.0
    return "{:.1f} PB".format(n)  # pragma: no cover


_SIZE_RE = re.compile(r"^\s*([0-9]+(?:\.[0-9]+)?)\s*([kKmMgGtTpP]?i?[bB]?)\s*$")
_FACTORS = {
    "": 1, "b": 1,
    "k": 10 ** 3, "kb": 10 ** 3, "kib": 2 ** 10,
    "m": 10 ** 6, "mb": 10 ** 6, "mib": 2 ** 20,
    "g": 10 ** 9, "gb": 10 ** 9, "gib": 2 ** 30,
    "t": 10 ** 12, "tb": 10 ** 12, "tib": 2 ** 40,
    "p": 10 ** 15, "pb": 10 ** 15, "pib": 2 ** 50,
}


def parse_size(text):
    """Parse sizes like '2.34GB', '512kB', '1.5 GiB' or '0B'. Returns bytes or None."""
    if text is None:
        return None
    m = _SIZE_RE.match(str(text))
    if not m:
        return None
    factor = _FACTORS.get(m.group(2).lower())
    if factor is None:
        return None
    return int(float(m.group(1)) * factor)


def parse_threshold(text):
    """Parse a percentage such as '85' or '85%'."""
    value = float(str(text).strip().rstrip("%"))
    if not 0 <= value <= 100:
        raise ValueError("percentage must be between 0 and 100")
    return value
