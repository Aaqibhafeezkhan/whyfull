"""Libvirt disk images, with conservative reference and backing-chain checks."""

import json
import posixpath
import shlex
import stat

from whyfull.checks import check
from whyfull.model import CAUTION, INFO, Finding
from whyfull.units import human
from whyfull.walk import allocated

ROOT = "/var/lib/libvirt/images"
MIN_BYTES = 10 ** 9


def _references(ctx):
    if not ctx.system.has("virsh"):
        return None
    names = ctx.system.run(["virsh", "list", "--all", "--name"])
    if names is None:
        return None
    sources = set()
    for name in names.splitlines():
        if not name.strip():
            continue
        text = ctx.system.run(["virsh", "domblklist", name.strip(), "--details"])
        if text is None or "Source" not in text:
            return None
        for line in text.splitlines():
            parts = line.split(None, 3)
            if not parts or parts[0] == "Type" or set(line.strip()) == {"-"}:
                continue
            if len(parts) != 4:
                return None
            kind, _device, _target, source = parts
            if kind == "file" and source != "-":
                if not posixpath.isabs(source):
                    return None
                sources.add(source)
    references = set(sources)
    for source in sources:
        # A disk can be used through another disk's qcow2 backing chain.
        # Without a complete chain, don't suggest that unlisted files are unused.
        if not ctx.system.has("qemu-img"):
            return None
        text = ctx.system.run(["qemu-img", "info", "--backing-chain", "--output=json", source])
        try:
            chain = json.loads(text or "null")
            if not isinstance(chain, list) or not chain:
                return None
            for item in chain:
                if not isinstance(item, dict) or not isinstance(item.get("filename"), str):
                    return None
                for key in ("filename", "full-backing-filename"):
                    value = item.get(key)
                    if value:
                        if not isinstance(value, str):
                            return None
                        references.add(value if posixpath.isabs(value)
                                       else posixpath.join(posixpath.dirname(source), value))
        except (ValueError, TypeError):
            return None
    return references


@check("libvirt", "Unreferenced libvirt disk images")
def run(ctx):
    directory = ctx.system.lstat(ROOT)
    if directory is None or not stat.S_ISDIR(directory.st_mode) or not ctx.on_target(ROOT):
        return
    images = []
    for name in ctx.system.listdir(ROOT):
        if not name.endswith((".qcow2", ".img")):
            continue
        path = posixpath.join(ROOT, name)
        info = ctx.system.lstat(path)
        if info is not None and stat.S_ISREG(info.st_mode) and ctx.on_target(path):
            size = allocated(info)
            if size >= MIN_BYTES:
                images.append((size, path, info))
    if not images:
        return
    references = _references(ctx)
    if references is None:
        yield Finding(
            "libvirt", ROOT, "Libvirt disk images (usage inventory unavailable)",
            sum(size for size, _, _ in images), INFO, ctx.dev_of(ROOT),
            detail=("Could not verify all VM disk references and backing chains. "
                    "These bytes are occupied storage, not an estimate of reclaimable space."),
            fix=["sudo virsh list --all", "# Check each VM's disks and backing chains before removing any image."],
            evidence=["%s  %s" % (human(size), path) for size, path, _ in sorted(images, reverse=True)[:5]],
        )
        return
    identities = set()
    for ref in references:
        info = ctx.system.stat(ref)
        if info is not None:
            identities.add((info.st_dev, info.st_ino))
    for size, path, info in sorted(images, key=lambda item: (-item[0], item[1])):
        if path in references or (info.st_dev, info.st_ino) in identities:
            continue
        yield Finding(
            "libvirt", path, "Libvirt disk image not referenced by a defined VM", size, CAUTION, info.st_dev,
            detail=("No defined VM or inspected backing chain references this file. "
                    "It may still belong to an external VM or backup; removing it destroys its contents."),
            fix=["sudo virsh list --all", "sudo qemu-img info %s" % shlex.quote(path),
                 "# Verify ownership and backups before running the removal command.",
                 "sudo rm -- %s" % shlex.quote(path)],
            evidence=["%s  %s" % (human(size), path)],
        )
