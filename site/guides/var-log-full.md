---
title: /var/log is full: what's safe to delete
description: Find the biggest files in /var/log, delete rotated and compressed logs safely, empty live logs without breaking the services writing them, and set up logrotate so it doesn't happen again.
short: Which logs you can delete, and which to truncate.
---

When `/var/log` fills a disk, it's usually one of three things: one log that grew huge because something is logging an error in a loop, years of rotated logs nobody cleaned up, or the systemd journal.

## Find the big files

```sh
sudo du -xh /var/log 2>/dev/null | sort -h | tail -20
sudo find /var/log -xdev -type f -size +100M -exec ls -lh {} \;
```

If `/var/log/journal` is at the top, see [the systemd journal guide](../journalctl-disk-usage/).

## Rotated logs: safe to delete

Files with a number or a date at the end, or a compression extension, are old rotated logs: `syslog.2.gz`, `nginx/access.log.1`, `messages-20261001`. Nothing writes to them any more, so deleting them is safe, as long as you don't need them for an audit.

```sh
sudo find /var/log -xdev -type f -regextype posix-extended \
  -regex '.*(\.(gz|xz|bz2|zst|old)|\.[0-9]+|-[0-9]{8})$' -print
```

Check the list, then run the same command with `-delete` in place of `-print`.

## Live logs: truncate, don't delete

A log that a service is writing to right now has no number at the end: `syslog`, `nginx/error.log`, `app.log`. Deleting it with `rm` doesn't free the space while the service still has it open (see [deleted files still using space](../deleted-files-still-using-space/)). Empty it instead:

```sh
sudo truncate -s 0 /var/log/app/app.log
```

Then find out why it grew. A log that gains gigabytes a day usually has the same error repeated over and over:

```sh
sudo tail -n 50 /var/log/app/app.log
```

## Files that look big but aren't

`/var/log/lastlog` can look enormous in `ls -l`. It's a sparse file indexed by user ID, so most of it isn't stored on disk. `du -h /var/log/lastlog` shows the real usage. The same goes for `faillog`.

## Make logrotate handle it

Most distributions rotate logs weekly. For a log that grows quickly, rotate it by size as well. In `/etc/logrotate.d/app`:

```
/var/log/app/*.log {
    daily
    maxsize 200M
    rotate 7
    compress
    missingok
    notifempty
    copytruncate
}
```

`copytruncate` is for programs that can't be told to reopen their log file. If the service supports a reload signal, use a `postrotate` script instead. Test the config without changing anything:

```sh
sudo logrotate -d /etc/logrotate.d/app
```
