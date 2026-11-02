#!/usr/bin/env python3
"""Build a realistic "disk full" server inside a directory and run whyfull on it.

Usage (as root, on Linux):

    truncate -s 4G /tmp/demo.img && mkfs.ext4 -q -F /tmp/demo.img
    mkdir -p /mnt/demo && mount -o loop /tmp/demo.img /mnt/demo
    python3 tools/demo.py /mnt/demo            # build it and print the report
    python3 tools/demo.py /mnt/demo --color    # same, with colours (for screenshots)

Everything is created under the given directory, which is treated as /. A
background process holds a deleted log file open, exactly like a service
whose log was removed by hand. The Docker daemon is not needed: the demo
answers `docker system df` with canned output.
"""

import argparse
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from whyfull.analyze import analyze  # noqa: E402
from whyfull.render import text  # noqa: E402
from whyfull.system import System  # noqa: E402

MB = 10 ** 6
DAY = 86400
CONTAINER = "4f2a9c1e5b7d" + "0" * 52

DOCKER_DF = "\n".join([
    '{"Active":"3","Reclaimable":"412MB (61%)","Size":"675MB","TotalCount":"9","Type":"Images"}',
    '{"Active":"3","Reclaimable":"0B (0%)","Size":"48kB","TotalCount":"3","Type":"Containers"}',
    '{"Active":"1","Reclaimable":"0B (0%)","Size":"95MB","TotalCount":"1","Type":"Local Volumes"}',
    '{"Active":"0","Reclaimable":"238MB","Size":"238MB","TotalCount":"57","Type":"Build Cache"}',
]) + "\n"


def blob(root, path, size, age_days=0):
    full = os.path.join(root, path.lstrip("/"))
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "wb") as f:
        f.truncate(0)
    subprocess.check_call(["fallocate", "-l", str(int(size)), full])
    if age_days:
        t = time.time() - age_days * DAY
        os.utime(full, (t, t))
    return full


def write(root, path, content):
    full = os.path.join(root, path.lstrip("/"))
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w") as f:
        f.write(content)


def build(root):
    # A deleted access log that "nginx" still has open (started first, so it can't be seen by du).
    log = blob(root, "/var/log/nginx/access.log", 700 * MB)
    holder = subprocess.Popen([
        sys.executable, "-c",
        "import os,sys,time\n"
        "open('/proc/self/comm','w').write('nginx')\n"
        "f=open(sys.argv[1],'ab'); os.unlink(sys.argv[1]); print('ready',flush=True); time.sleep(3600)",
        log], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL)
    if holder.stdout.readline().strip() != b"ready":
        holder.kill()
        raise SystemExit("demo: the process holding the deleted log failed to start")
    try:
        build_rest(root)
    except BaseException:
        holder.kill()
        raise
    return holder


def build_rest(root):

    # systemd journal, 640 MB
    for i in range(8):
        blob(root, "/var/log/journal/9f0c8e/system@%02d.journal" % i, 70 * MB, age_days=30 - i)
    # rotated syslog and nginx logs
    for i, name in enumerate(["syslog.2.gz", "syslog.3.gz", "syslog.4.gz", "nginx/access.log.2.gz",
                              "nginx/access.log.3.gz", "auth.log.1", "kern.log.1"]):
        blob(root, "/var/log/" + name, 40 * MB, age_days=7 * (i + 1))
    # a container that logs too much
    blob(root, "/var/lib/docker/containers/%s/%s-json.log" % (CONTAINER, CONTAINER), 560 * MB)
    write(root, "/var/lib/docker/containers/%s/config.v2.json" % CONTAINER, '{"Name": "/api"}')
    # apt cache
    for i in range(12):
        blob(root, "/var/cache/apt/archives/pkg%02d_1.0_amd64.deb" % i, 20 * MB)
    # kernels: two old ones besides the running and the newest
    for v in ("6.8.0-31-generic", "6.8.0-35-generic", "6.8.0-40-generic", "6.8.0-45-generic"):
        blob(root, "/lib/modules/%s/kernel/drivers.ko" % v, 70 * MB)
        blob(root, "/boot/vmlinuz-%s" % v, 10 * MB)
        blob(root, "/boot/initrd.img-%s" % v, 50 * MB)
    # user caches
    blob(root, "/home/alice/.cache/pip/http/cache.bin", 220 * MB)
    blob(root, "/home/alice/.m2/repository/org/big.jar", 150 * MB)
    blob(root, "/root/.npm/_cacache/content.bin", 100 * MB)
    # crash dumps and stale temp files
    blob(root, "/var/crash/_usr_bin_api.0.crash", 140 * MB, age_days=12)
    blob(root, "/tmp/build-7731/artifact.tar", 200 * MB, age_days=19)
    # real data that should not be touched
    blob(root, "/var/lib/postgresql/16/main/base.dat", 330 * MB)

    write(root, "/etc/os-release", 'ID=ubuntu\nID_LIKE=debian\nPRETTY_NAME="Ubuntu 24.04 LTS"\n')
    write(root, "/etc/passwd", "root:x:0:0:root:/root:/bin/bash\n"
                                "alice:x:1000:1000:Alice:/home/alice:/bin/bash\n")


def fake_proc(root, holder_pid):
    """A /proc that describes the demo disk as / and exposes the holder process."""
    proc = os.path.join(root, "proc")
    os.makedirs(os.path.join(proc, "self"), exist_ok=True)
    os.makedirs(os.path.join(proc, "sys", "kernel"), exist_ok=True)
    src = subprocess.check_output(["findmnt", "-no", "SOURCE", "--target", root],
                                  universal_newlines=True).strip()
    with open(os.path.join(proc, "self", "mountinfo"), "w") as f:
        f.write("22 1 7:0 / / rw,relatime - ext4 %s rw\n" % src)
    with open(os.path.join(proc, "sys", "kernel", "osrelease"), "w") as f:
        f.write("6.8.0-45-generic\n")
    # The holder's open files are real; its identity is staged so that it looks like
    # nginx running as a systemd service, whatever cgroup the demo itself runs in.
    entry = os.path.join(proc, str(holder_pid))
    if os.path.lexists(entry):
        subprocess.check_call(["rm", "-rf", entry])
    os.makedirs(entry)
    os.symlink("/proc/%d/fd" % holder_pid, os.path.join(entry, "fd"))
    with open(os.path.join(entry, "comm"), "w") as f:
        f.write("nginx\n")
    with open(os.path.join(entry, "cgroup"), "w") as f:
        f.write("0::/system.slice/nginx.service\n")
    return proc


def runner(argv):
    if argv[:2] == ["which", "docker"] or argv[:3] == ["docker", "system", "df"]:
        return DOCKER_DF if argv[0] == "docker" else "/usr/bin/docker"
    if argv[:2] == ["docker", "info"]:
        return "/var/lib/docker\n"
    return None


def main():
    p = argparse.ArgumentParser()
    p.add_argument("root")
    p.add_argument("--color", action="store_true")
    args = p.parse_args()
    root = os.path.abspath(args.root)
    holder = build(root)
    try:
        proc = fake_proc(root, holder.pid)
        system = System(root=root, proc=proc, runner=runner, euid=0)
        report = analyze(system, scan_seconds=60)
        sys.stdout.write(text(report, color=args.color, width=100))
    finally:
        holder.kill()


if __name__ == "__main__":
    main()
