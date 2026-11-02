---
title: The systemd journal is taking up too much disk space
description: Check how much space journald uses with journalctl --disk-usage, shrink it safely with --vacuum-size or --vacuum-time, and cap it with SystemMaxUse so it doesn't grow back.
short: Shrink /var/log/journal and keep it small.
---

On systemd distributions, `journald` stores logs in `/var/log/journal`, or in `/run/log/journal` if that directory doesn't exist. By default it may use up to 10% of the filesystem, capped at 4 GB. On a small root disk, or on a server where one service logs constantly, that's a lot of space for old logs.

## Check how much it uses

```sh
journalctl --disk-usage
```

```text
Archived and active journals take up 3.6G in the file system.
```

## Shrink it

Keep the newest 200 MB and delete older journal files:

```sh
sudo journalctl --vacuum-size=200M
```

Or keep only the last two weeks:

```sh
sudo journalctl --vacuum-time=2weeks
```

Vacuuming only removes archived journal files, not the ones currently being written. If it frees less than you expected, rotate first so the active files are archived too:

```sh
sudo journalctl --rotate
sudo journalctl --vacuum-size=200M
```

Don't delete files in `/var/log/journal` with `rm`. journald may still have them open, and then the space isn't freed (see [deleted files still using space](../deleted-files-still-using-space/)).

## Keep it capped

Vacuuming is a one-off. To set a permanent limit, add a drop-in file and restart journald:

```sh
sudo mkdir -p /etc/systemd/journald.conf.d
printf '[Journal]\nSystemMaxUse=200M\n' | sudo tee /etc/systemd/journald.conf.d/size.conf
sudo systemctl restart systemd-journald
```

`SystemMaxUse` caps `/var/log/journal`. Use `RuntimeMaxUse` instead if your system keeps the journal in `/run`. `SystemKeepFree` sets how much space journald must leave free on the disk, which is useful on small disks.

## Find what's flooding the journal

If the journal fills up again quickly, something is logging far too much. This shows which units wrote the most entries in the last hour:

```sh
journalctl --since "1 hour ago" -o json --output-fields=_SYSTEMD_UNIT \
  | grep -o '"_SYSTEMD_UNIT":"[^"]*"' | sort | uniq -c | sort -n | tail
```

Fixing that service's log level does more than any cap.
