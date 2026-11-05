"""Jenkins workspaces and build history, including jobs in folders."""

import posixpath
import stat

from whyfull.checks import check
from whyfull.model import REVIEW, Finding
from whyfull.units import human

ROOT = "/var/lib/jenkins"
MIN_BYTES = 10 ** 9


def _directory(ctx, path):
    info = ctx.system.lstat(path)
    return info is not None and stat.S_ISDIR(info.st_mode) and ctx.on_target(path)


@check("jenkins", "Jenkins workspaces and build history")
def run(ctx):
    if not _directory(ctx, ROOT):
        return
    workspace = posixpath.join(ROOT, "workspace")
    if _directory(ctx, workspace):
        size = ctx.size(workspace)
        if size >= MIN_BYTES:
            yield Finding(
                "jenkins", workspace, "Jenkins workspaces", size, REVIEW, ctx.dev_of(workspace),
                detail=("Includes active and inactive job workspaces. "
                        "Stop or finish running jobs before cleaning their workspaces."),
                fix=["# In Jenkins, review job workspaces and use the Workspace Cleanup plugin.",
                     "# Configure cleanWs() in the job's Pipeline rather than removing files behind Jenkins."],
                evidence=["%s  %s" % (human(size), workspace)],
            )
    stack = [(posixpath.join(ROOT, "jobs"), "")]
    histories = []
    while stack and not ctx.budget.expired():
        parent, prefix = stack.pop()
        if not _directory(ctx, parent):
            continue
        for name in ctx.system.listdir(parent):
            job = posixpath.join(parent, name)
            if not _directory(ctx, job):
                continue
            label = prefix + name
            builds = posixpath.join(job, "builds")
            if _directory(ctx, builds):
                size = ctx.size(builds)
                if size >= MIN_BYTES:
                    histories.append((size, builds, label, ctx.dev_of(builds)))
            stack.append((posixpath.join(job, "jobs"), label + "/"))
    for size, path, label, dev in sorted(histories, reverse=True)[:5]:
        yield Finding(
            "jenkins", path, "Jenkins build history for %s" % label, size, REVIEW, dev,
            detail=("Build records include logs and archived artifacts. Removing them loses history. "
                    "Choose a retention policy in Jenkins after checking which builds must be kept."),
            fix=["# Configure the job's Discard old builds setting in Jenkins.",
                 "# Pipeline equivalent: options { buildDiscarder(logRotator(numToKeepStr: '10')) }",
                 "# Review the retention count and artifact policy before applying it."],
            evidence=["%s  %s" % (human(size), path)],
        )
