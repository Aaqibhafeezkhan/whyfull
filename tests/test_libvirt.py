import json

import pytest

from conftest import make_ctx
from whyfull.checks import libvirt
from whyfull.model import CAUTION, INFO


def setup_images(root, monkeypatch):
    monkeypatch.setattr(libvirt, "MIN_BYTES", 20000)
    root.write(libvirt.ROOT + "/used.qcow2", size=50000)
    root.write(libvirt.ROOT + "/base.img", size=50000)
    root.write(libvirt.ROOT + "/orphan disk.qcow2", size=50000)


def inventory(root):
    used = libvirt.ROOT + "/used.qcow2"
    root.commands[("virsh", "list", "--all", "--name")] = "vm\n"
    root.commands[("virsh", "domblklist", "vm", "--details")] = (
        "Type Device Target Source\n-----------------------------\nfile disk vda %s\n" % used)
    # Only shared, read-only inspection is available for a running VM's image.
    root.commands[("qemu-img", "info", "-U", "--backing-chain", "--output=json", used)] = json.dumps([
        {"filename": used, "full-backing-filename": libvirt.ROOT + "/base.img"},
        {"filename": libvirt.ROOT + "/base.img"},
    ])


def test_used_disks_and_backing_images_are_preserved(root, monkeypatch):
    setup_images(root, monkeypatch)
    inventory(root)
    finding, = list(libvirt.run(make_ctx(root.system())))
    assert finding.key.endswith("orphan disk.qcow2")
    assert finding.risk == CAUTION
    assert "'" in finding.fix[-1]
    assert all(command[1] not in ("undefine", "destroy") for command in root.commands)


@pytest.mark.parametrize("broken", [None, "bad-json", "{}", "[]", '[{"filename":3}]'])
def test_incomplete_backing_chain_is_information_only(root, monkeypatch, broken):
    setup_images(root, monkeypatch)
    inventory(root)
    root.commands[("qemu-img", "info", "-U", "--backing-chain", "--output=json", libvirt.ROOT + "/used.qcow2")] = broken
    finding, = list(libvirt.run(make_ctx(root.system())))
    assert finding.risk == INFO
    assert not any("rm " in line for line in finding.fix)


def test_missing_virsh_is_information_only(root, monkeypatch):
    setup_images(root, monkeypatch)
    finding, = list(libvirt.run(make_ctx(root.system())))
    assert finding.risk == INFO


def test_failed_vm_inventory_does_not_claim_unused_images(root, monkeypatch):
    setup_images(root, monkeypatch)
    root.commands[("virsh", "list", "--all", "--name")] = "vm\n"
    assert list(libvirt.run(make_ctx(root.system())))[0].risk == INFO


def test_no_defined_vms_reports_candidates_cautiously(root, monkeypatch):
    setup_images(root, monkeypatch)
    root.commands[("virsh", "list", "--all", "--name")] = ""
    assert len(list(libvirt.run(make_ctx(root.system())))) == 3


def test_missing_small_and_other_filesystems_are_silent(root, monkeypatch):
    assert list(libvirt.run(make_ctx(root.system()))) == []
    setup_images(root, monkeypatch)
    root.mounts.append((libvirt.ROOT, "ext4", "/dev/sdb1"))
    assert list(libvirt.run(make_ctx(root.system()))) == []
