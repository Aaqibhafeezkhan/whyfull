import json
import os

import pytest
from conftest import GB

from whyfull import cli
from whyfull.analyze import analyze
from whyfull.checks import REGISTRY, Check
from whyfull.model import INFO, Filesystem
from whyfull.mounts import parse_mountinfo
from whyfull.render import as_json, markdown, text
from whyfull.units import human, parse_size, parse_threshold
from whyfull.walk import Budget, du, scan


def test_human():
    assert human(0) == "0 B"
    assert human(999) == "999 B"
    assert human(1500) == "1.5 KB"
    assert human(14200000000) == "14.2 GB"
    assert human(700 * 10 ** 6) == "700 MB"
    assert human(99.96 * 10 ** 6) == "100 MB"


def test_parse_size():
    assert parse_size("2.34GB") == 2340000000
    assert parse_size("512kB") == 512000
    assert parse_size("1GiB") == 2 ** 30
    assert parse_size("0B") == 0
    assert parse_size("lots") is None


def test_parse_threshold():
    assert parse_threshold("85%") == 85
    with pytest.raises(ValueError):
        parse_threshold("120")


def test_df_style_percent():
    fs = Filesystem("/", "/dev/x", "ext4", 1, size=100, used=90, avail=5)
    assert fs.percent == 95  # used / (used + avail), rounded up, like df
    fs.avail = 0
    assert fs.percent == 100


def test_parse_mountinfo_unescapes_spaces():
    text = ("36 25 8:1 / / rw,relatime shared:1 - ext4 /dev/sda1 rw\n"
            "40 36 8:2 / /mnt/my\\040disk rw - xfs /dev/sdb1 rw\n")
    assert list(parse_mountinfo(text)) == [("/", "ext4", "/dev/sda1"), ("/mnt/my disk", "xfs", "/dev/sdb1")]


def test_du_counts_hard_links_once(tmp_path):
    a = tmp_path / "a"
    a.write_bytes(os.urandom(8192))
    os.link(str(a), str(tmp_path / "b"))
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "c").write_bytes(os.urandom(4096))
    usage = du(str(tmp_path))
    assert usage.files == 2
    assert usage.bytes >= 12288


def test_du_stops_at_budget(tmp_path):
    for i in range(5):
        (tmp_path / str(i)).mkdir()
        (tmp_path / str(i) / "f").write_bytes(b"x" * 10)
    budget = Budget(0.000001)
    import time
    time.sleep(0.01)
    assert du(str(tmp_path), budget=budget).complete is False


def test_scan_rolls_up_sizes_and_finds_crowded_dirs(tmp_path):
    (tmp_path / "var/lib/app").mkdir(parents=True)
    (tmp_path / "var/lib/app/data").write_bytes(os.urandom(40960))
    (tmp_path / "var/lib/app/deep/er/still").mkdir(parents=True)
    (tmp_path / "var/lib/app/deep/er/still/f").write_bytes(os.urandom(8192))
    (tmp_path / "sessions").mkdir()
    for i in range(50):
        (tmp_path / "sessions" / ("s%d" % i)).write_bytes(b"x")
    tree = scan(str(tmp_path), os.stat(str(tmp_path)).st_dev)
    assert tree.complete
    var = tree.sizes[str(tmp_path / "var")]
    assert var == tree.sizes[str(tmp_path / "var/lib")] == tree.sizes[str(tmp_path / "var/lib/app")]
    assert var >= 40960 + 8192
    assert tree.sizes[str(tmp_path)] == tree.total
    assert tree.crowded[0] == (50, str(tmp_path / "sessions"))


def test_analyze_picks_full_filesystems(root):
    root.mounts.append(("/data", "xfs", "/dev/sdb1"))
    root.set_usage("/", used=50 * GB)
    root.set_usage("/data", used=97 * GB)
    report = analyze(root.system(), scan_seconds=10)
    assert [t.fs.mountpoint for t in report.targets] == ["/data"]
    assert not report.all_clear


def test_analyze_all_clear_shows_root(root):
    root.set_usage("/", used=10 * GB)
    report = analyze(root.system(), scan_seconds=10)
    assert report.all_clear
    assert report.targets[0].fs.mountpoint == "/"


def test_unexplained_space_points_at_hidden_mounts(root):
    root.mounts.append(("/data", "xfs", "/dev/sdb1"))
    root.set_usage("/", used=40 * GB)
    root.set_usage("/data", used=10 * GB)
    report = analyze(root.system(), paths=["/"], scan_seconds=10)
    gap = [f for f in report.targets[0].findings if f.check == "unexplained"]
    # fake usage says 40 GB but the tree holds a few KB: the gap must be explained
    assert len(gap) == 1 and gap[0].risk == INFO
    assert any("/mnt/whyfull-under/data" in c for c in gap[0].fix)


def test_broken_check_does_not_hide_the_rest(root, monkeypatch):
    def boom(ctx):
        raise RuntimeError("kaput")
    monkeypatch.setattr("whyfull.checks.REGISTRY", REGISTRY + [Check("boom", "always fails", boom)])
    monkeypatch.setattr("whyfull.checks.MODULES", [])
    report = analyze(root.system(), paths=["/"], scan_seconds=5)
    assert report.errors == [("boom", "RuntimeError: kaput")]


def test_renderers(root):
    root.write("/var/log/x.log", size=1000)
    report = analyze(root.system(), paths=["/"], scan_seconds=5)
    out = text(report, color=False)
    assert "/ is 90% full" in out
    assert "never deletes anything" in out
    assert "\033[" not in out
    assert "\033[" in text(report, color=True)
    data = json.loads(as_json(report, None))
    assert data["targets"][0]["filesystem"]["mountpoint"] == "/"
    assert "### / is 90% full" in markdown(report)


def test_cli_json_and_exit_codes(root, capsys):
    root.system()  # writes the fake /proc
    root.set_usage("/", used=95 * GB)
    assert cli.main(["--root", root.path, "--json", "--scan-time", "5"]) == 0
    # --root uses the real statvfs of the fake root's directory, so only check the shape
    assert "targets" in json.loads(capsys.readouterr().out)
    assert cli.main(["--root", root.path, "--only", "nope"]) == 2
    assert cli.main(["--root", root.path, "--threshold", "150"]) == 2
    assert cli.main(["--list-checks"]) == 0
    assert "deleted-open" in capsys.readouterr().out
    assert cli.main(["--root", root.path, "--fail-above", "0", "--scan-time", "5"]) == 1
