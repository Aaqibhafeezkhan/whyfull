"""Package manager download caches."""

from whyfull.checks import check
from whyfull.model import SAFE, Finding

MIN_BYTES = 100 * 10 ** 6

CACHES = [
    # (path, manager, binary, fix)
    ("/var/cache/apt/archives", "apt", "apt-get", "sudo apt-get clean"),
    ("/var/cache/dnf", "dnf", "dnf", "sudo dnf clean all"),
    ("/var/cache/yum", "yum", "yum", "sudo yum clean all"),
    ("/var/cache/pacman/pkg", "pacman", "pacman", "sudo pacman -Sc"),
    ("/var/cache/zypp/packages", "zypper", "zypper", "sudo zypper clean --all"),
    ("/var/cache/apk", "apk", "apk", "sudo apk cache clean"),
]


@check("packages", "Package manager caches")
def run(ctx):
    for path, manager, _binary, fix in CACHES:
        if not ctx.system.exists(path) or not ctx.on_target(path):
            continue
        size = ctx.size(path)
        if size < MIN_BYTES:
            continue
        yield Finding(
            "packages", manager, "%s package cache in %s" % (manager, path), size, SAFE,
            ctx.dev_of(path),
            detail="Downloaded package files kept after installing. They are fetched again if needed.",
            fix=[fix],
        )
