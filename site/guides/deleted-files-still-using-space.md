---
title: Deleted files still using disk space on Linux
description: You deleted a big log file but the disk didn't get any emptier. Find deleted files that are still held open with lsof or /proc, and free the space with or without restarting the service.
short: You deleted it, but the space never came back.
---

You deleted a 20 GB log file with `rm`, ran `df -h` again, and nothing changed. The file is gone from the directory, yet the disk is just as full.

## Why this happens

On Linux, a file's name and its data are separate. `rm` removes the name. The data is only freed when nothing refers to it any more, and a process that has the file open still refers to it. So when a running service is writing to a log and someone deletes that log, the service keeps writing into a file that no longer has a name, and the space stays in use until the service closes it or exits.

This also explains why `du` can't find the space: `du` walks names, and the file doesn't have one.

## Find the deleted files and who holds them

```sh
sudo lsof +L1
```

This lists open files whose link count is below 1, meaning they've been deleted. The output shows the process name (`COMMAND`), its `PID`, the file descriptor (`FD`, for example `7w`) and the size. To list only the big ones, sorted by size:

```sh
sudo lsof -nP +L1 | awk 'NR > 1 { print $7, $1, $2, $4, $10 }' | sort -n | tail
```

Without `lsof`, read `/proc` directly. Each entry is a symlink that ends in `(deleted)`:

```sh
sudo find /proc/*/fd -ls 2>/dev/null | grep '(deleted)'
```

The path tells you the PID and the descriptor number: `/proc/1234/fd/7` is descriptor 7 of process 1234.

## Free the space

**Restart the process.** This is the cleanest fix. If it's a systemd service, find which unit owns the process and restart that:

```sh
systemctl status 1234          # the first line names the unit
sudo systemctl restart nginx
```

If the process runs in a Docker container, `docker restart <container>` does the same job.

**Empty the file without a restart.** When restarting isn't an option right now, truncate the open file through `/proc`. The process keeps running, and the space is freed immediately:

```sh
sudo truncate -s 0 /proc/1234/fd/7
```

The process keeps its position in the file, so the file may grow back as a sparse file. It looks large in `ls`, but it only uses the space that new writes take. A restart later cleans that up.

## Stop it happening again

- Don't `rm` a log file that a service is writing. Truncate it instead: `sudo truncate -s 0 /var/log/app.log`.
- Let logrotate do the rotating. Its default (`create`) renames the file and tells the service to reopen it. For programs that can't reopen their logs, use `copytruncate`.
- For Docker, set log rotation in `/etc/docker/daemon.json` so container logs never grow without limit. See [Docker disk space](../docker-disk-space/).
