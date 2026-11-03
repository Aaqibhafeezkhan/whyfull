import os

from conftest import make_ctx
from whyfull.checks import jenkins
from whyfull.model import REVIEW


def test_nested_jobs_and_workspace(root, monkeypatch):
    monkeypatch.setattr(jenkins, "MIN_BYTES", 20000)
    root.write("/var/lib/jenkins/workspace/job/output", size=50000)
    root.write("/var/lib/jenkins/jobs/team/jobs/job/builds/1/log", size=60000)
    findings = list(jenkins.run(make_ctx(root.system())))
    assert len(findings) == 2
    assert findings[0].title == "Jenkins workspaces"
    assert "team/job" in findings[1].title
    assert all(f.risk == REVIEW for f in findings)
    assert all(line.startswith("#") for f in findings for line in f.fix)
    assert root.commands == {}


def test_small_histories_and_missing_installation(root, monkeypatch):
    monkeypatch.setattr(jenkins, "MIN_BYTES", 20000)
    assert list(jenkins.run(make_ctx(root.system()))) == []
    root.write("/var/lib/jenkins/jobs/tiny/builds/1/log", size=100)
    assert list(jenkins.run(make_ctx(root.system()))) == []


def test_other_filesystems_are_not_reported(root, monkeypatch):
    monkeypatch.setattr(jenkins, "MIN_BYTES", 20000)
    path = "/var/lib/jenkins/jobs/job/builds"
    root.write(path + "/1/log", size=50000)
    root.mounts.append((path, "ext4", "/dev/sdb1"))
    assert list(jenkins.run(make_ctx(root.system()))) == []


def test_symlinked_jobs_are_skipped(root, monkeypatch):
    monkeypatch.setattr(jenkins, "MIN_BYTES", 20000)
    root.write("/data/job/builds/1/log", size=50000)
    root.mkdir("/var/lib/jenkins/jobs")
    os.symlink(root.local("/data/job"), root.local("/var/lib/jenkins/jobs/link"))
    assert list(jenkins.run(make_ctx(root.system()))) == []


def test_only_largest_five_build_histories(root, monkeypatch):
    monkeypatch.setattr(jenkins, "MIN_BYTES", 20000)
    for i in range(7):
        root.write("/var/lib/jenkins/jobs/job%d/builds/1/log" % i, size=30000 + i * 10000)
    findings = list(jenkins.run(make_ctx(root.system())))
    assert len(findings) == 5
    assert [f.bytes for f in findings] == sorted([f.bytes for f in findings], reverse=True)


def test_expired_budget_stops_job_walk(root, monkeypatch):
    root.write("/var/lib/jenkins/jobs/job/builds/1/log", size=50000)
    ctx = make_ctx(root.system())
    monkeypatch.setattr(ctx.budget, "expired", lambda: True)
    assert list(jenkins.run(ctx)) == []
