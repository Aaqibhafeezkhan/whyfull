"""Docker images, build cache, stopped containers, volumes and container logs."""

import json
import os

from whyfull.checks import check
from whyfull.model import CAUTION, REVIEW, SAFE, Finding
from whyfull.units import human, parse_size

MIN_RECLAIM = 200 * 10 ** 6
BIG_LOG = 500 * 10 ** 6

# docker system df row type -> (risk, title, fix, detail)
DF_ROWS = {
    "Build Cache": (
        SAFE, "Docker build cache", ["docker builder prune -f"],
        "Layers cached by docker build. They are rebuilt on the next build that needs them.",
    ),
    "Images": (
        REVIEW, "Docker images not used by any container", ["docker image prune -a -f"],
        "Images with no container using them. They are pulled again if something needs them later.",
    ),
    "Containers": (
        REVIEW, "Stopped Docker containers", ["docker container prune -f"],
        "Writable layers of containers that have exited. Check nothing needs to be restarted from them.",
    ),
    "Local Volumes": (
        CAUTION, "Docker volumes not used by any container", ["docker volume ls -f dangling=true  # look first",
                                                               "docker volume prune -f"],
        "Volumes hold data such as databases. Unused ones may still matter: inspect before pruning.",
    ),
}


def docker_root(ctx):
    out = ctx.system.run(["docker", "info", "--format", "{{.DockerRootDir}}"])
    root = (out or "").strip()
    return root or "/var/lib/docker"


@check("docker", "Docker images, build cache, containers and volumes")
def docker(ctx):
    root = docker_root(ctx)
    if not ctx.system.exists(root) or not ctx.on_target(root):
        return
    dev = ctx.dev_of(root)
    out = ctx.system.run(["docker", "system", "df", "--format", "{{json .}}"], timeout=60)
    if out is None:
        ctx.note("Docker data lives on this disk, but `docker system df` didn't run; "
                 "run whyfull with sudo or as a member of the docker group to include it.")
    else:
        for line in out.splitlines():
            try:
                row = json.loads(line)
            except ValueError:
                continue
            spec = DF_ROWS.get(row.get("Type"))
            if spec is None:
                continue
            reclaim = parse_size(str(row.get("Reclaimable", "")).split(" (")[0])
            if not reclaim or reclaim < MIN_RECLAIM:
                continue
            risk, title, fix, detail = spec
            yield Finding("docker", row["Type"].lower().replace(" ", "-"), title, reclaim, risk, dev,
                          detail=detail, fix=fix,
                          evidence=["%s total, %s in use" % (row.get("TotalCount", "?"), row.get("Active", "?"))])

    # Container logs are not in `docker system df`; read them from disk.
    logs = []
    containers = os.path.join(root, "containers")
    for cid in ctx.system.listdir(containers):
        log = os.path.join(containers, cid, cid + "-json.log")
        st = ctx.system.stat(log)
        if st is None or st.st_size < BIG_LOG:
            continue
        name = cid[:12]
        cfg = ctx.system.read_text(os.path.join(containers, cid, "config.v2.json"))
        if cfg:
            try:
                name = json.loads(cfg).get("Name", "").lstrip("/") or name
            except ValueError:
                pass
        logs.append((st.st_blocks * 512, name, log))
    logs.sort(reverse=True)
    for size, name, _log in logs[:5]:
        yield Finding(
            "docker", "log:" + name, "Docker log of container %s is %s" % (name, human(size)),
            size, CAUTION, dev,
            detail=("The json-file log driver keeps everything a container prints unless "
                    "max-size is set. Truncating loses that history; set rotation so it doesn't grow back."),
            fix=["sudo truncate -s 0 \"$(docker inspect --format '{{.LogPath}}' %s)\"" % name,
                 "# rotate future logs (applies to new containers): add to /etc/docker/daemon.json",
                 '#   {"log-driver": "json-file", "log-opts": {"max-size": "50m", "max-file": "3"}}'],
        )
