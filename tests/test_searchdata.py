import stat

import pytest

from conftest import make_ctx
from whyfull.checks import load
from whyfull.model import INFO


PATHS = ("/var/lib/elasticsearch", "/var/lib/opensearch")
LARGE = 6 * 10 ** 9


def search_findings(ctx):
    return [finding for check in load() if check.id == "search-data"
            for finding in check.fn(ctx)]


@pytest.mark.parametrize("directory", PATHS)
def test_search_data_is_informational_and_runs_no_commands(root, monkeypatch, directory):
    root.write(directory + "/nodes/0/index", size=60000)
    system = root.system()

    def no_commands(argv, **kwargs):
        pytest.fail("check must not execute a command: %r" % (argv,))

    monkeypatch.setattr(system, "run", no_commands)
    ctx = make_ctx(system)
    monkeypatch.setattr(ctx, "size", lambda path: LARGE)
    found = search_findings(ctx)
    assert len(found) == 1
    finding = found[0]
    assert finding.key == directory
    assert finding.bytes == LARGE
    assert finding.risk == INFO
    assert "Never delete" in finding.detail
    assert "may be read-only" not in finding.detail
    assert any("_cat/indices" in command for command in finding.fix)
    assert not any("rm " in command or "DELETE" in command for command in finding.fix)


@pytest.mark.parametrize("used,avail,warning", [(94, 6, False), (95, 5, True), (100, 0, True)])
def test_search_data_flood_stage_is_only_a_configurable_hint(root, monkeypatch, used, avail, warning):
    root.write(PATHS[0] + "/nodes/index", size=60000)
    ctx = make_ctx(root.system())
    ctx.targets[0].used = used
    ctx.targets[0].avail = avail
    monkeypatch.setattr(ctx, "size", lambda path: LARGE)
    found = search_findings(ctx)
    assert len(found) == 1
    assert ("may be read-only" in found[0].detail) == warning
    if warning:
        assert "configured" in found[0].detail
        assert "below the high watermark" in found[0].detail


def test_search_data_ignores_missing_small_and_regular_file_paths(root, monkeypatch):
    ctx = make_ctx(root.system())
    assert search_findings(ctx) == []
    root.write(PATHS[0], size=20000)
    root.write(PATHS[1] + "/nodes/index", size=20000)
    monkeypatch.setattr(ctx, "size", lambda path: 5 * 10 ** 9 - 1)
    assert search_findings(ctx) == []


def test_search_data_skips_other_filesystems_before_measuring(root, monkeypatch):
    root.write(PATHS[0] + "/nodes/index", size=60000)
    root.mounts.append((PATHS[0], "ext4", "/dev/sdb1"))
    ctx = make_ctx(root.system())

    def no_measurement(path):
        pytest.fail("off-target path was measured: %s" % path)

    monkeypatch.setattr(ctx, "size", no_measurement)
    assert search_findings(ctx) == []


def test_search_data_skips_symlink_roots(root, monkeypatch):
    root.write(PATHS[0] + "/nodes/index", size=60000)
    ctx = make_ctx(root.system())
    original = ctx.system.lstat

    class LinkStat(object):
        st_mode = stat.S_IFLNK

    monkeypatch.setattr(ctx.system, "lstat", lambda path: LinkStat() if path == PATHS[0] else original(path))
    monkeypatch.setattr(ctx, "size", lambda path: pytest.fail("symlink root measured"))
    assert search_findings(ctx) == []


def test_search_data_measures_the_fake_store(root, monkeypatch):
    from whyfull.checks import searchdata

    monkeypatch.setattr(searchdata, "MIN_BYTES", 20000)
    root.write(PATHS[0] + "/nodes/index", size=60000)
    ctx = make_ctx(root.system())
    found = search_findings(ctx)
    assert len(found) == 1
    assert found[0].bytes == ctx.size(PATHS[0])
    assert found[0].bytes >= 60000
