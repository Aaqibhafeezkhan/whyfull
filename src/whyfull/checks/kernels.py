"""Old kernels: their modules under /lib/modules and their images in /boot."""

import os
import re

from whyfull.checks import check
from whyfull.model import REVIEW, Finding
from whyfull.units import human

MIN_BYTES = 50 * 10 ** 6
BOOT_PATTERNS = ["vmlinuz-%s", "initrd.img-%s", "initramfs-%s.img", "initramfs-%skdump.img",
                 "System.map-%s", "config-%s", "abi-%s", "retpoline-%s"]

FIXES = {
    "debian": ["sudo apt autoremove --purge",
               "# if old kernels remain, purge them by name, e.g.: sudo apt purge linux-image-%(v)s"],
    "rhel": ["sudo dnf remove --oldinstallonly --setopt installonly_limit=2 kernel"],
    "suse": ["sudo zypper purge-kernels"],
}


def version_key(v):
    return [int(p) if p.isdigit() else p for p in re.split(r"(\d+)", v)]


def installed(ctx):
    """Kernel versions with a modules directory, and where each directory is."""
    found = {}
    for base in ("/lib/modules", "/usr/lib/modules"):
        for v in ctx.system.listdir(base):
            path = os.path.join(base, v)
            local = ctx.system.path(path)
            if not os.path.isdir(local):
                continue
            real = os.path.realpath(local)
            if any(os.path.realpath(ctx.system.path(p)) == real for p in found.values()):
                continue
            found.setdefault(v, path)
    return found


@check("kernels", "Old kernels")
def run(ctx):
    kernels = installed(ctx)
    if len(kernels) < 2:
        return
    running = ctx.system.kernel_release()
    newest = max(kernels, key=version_key)
    old = sorted((v for v in kernels if v not in (running, newest)), key=version_key)
    if not old:
        return

    per_dev = {}  # dev -> [bytes, versions]
    for v in old:
        parts = [kernels[v]] + ["/boot/" + p % v for p in BOOT_PATTERNS]
        for path in parts:
            if not ctx.system.exists(path) or not ctx.on_target(path):
                continue
            entry = per_dev.setdefault(ctx.dev_of(path), [0, set()])
            entry[0] += ctx.size(path)
            entry[1].add(v)

    family = ctx.system.distro_family()
    for dev, (nbytes, versions) in per_dev.items():
        if nbytes < MIN_BYTES:
            continue
        versions = sorted(versions, key=version_key)
        fs = ctx.filesystem(dev)
        where = " in /boot" if fs is not None and fs.mountpoint == "/boot" else ""
        fix = [f % {"v": versions[0]} for f in FIXES.get(family, [])] or \
            ["# remove the kernel packages for: " + ", ".join(versions)]
        yield Finding(
            "kernels", str(dev), "%d old kernel%s%s" % (len(versions), "" if len(versions) == 1 else "s", where),
            nbytes, REVIEW, dev,
            detail=("Kernels other than the running one (%s) and the newest (%s). Package managers keep "
                    "them as fallbacks; one spare is plenty. A full /boot can make kernel updates fail."
                    % (running, newest)),
            fix=fix,
            evidence=["%s" % v for v in versions[:8]],
        )
    if per_dev and not any(b >= MIN_BYTES for b, _ in per_dev.values()):
        ctx.note("Old kernels found but they are small (%s)." % human(sum(b for b, _ in per_dev.values())))
