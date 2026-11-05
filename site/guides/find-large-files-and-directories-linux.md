---
title: Find large files and directories on Linux
description: Use du, find, and ncdu to find what is actually using disk space on Linux, from the top-level directories down to individual files, without deleting anything yet.
short: du, find, and ncdu, top-down.
---

When a disk is full, the first job is finding where the space went, not
deleting things. Work top-down: find the biggest directory, then the
biggest directory inside it, until you reach individual files. Only then
decide what is safe to remove. Everything in this guide only reads the
disk; nothing here deletes anything.

## 1. See what's full

```sh
df -h
```

`df -h` shows space per filesystem. Note which filesystem is full
(usually `/`) before searching: searching a different filesystem wastes
time and can report files that are not part of the problem.

## 2. Find the biggest top-level directories

```sh
sudo du -xh --max-depth=1 / | sort -h
```

- `-x` keeps `du` on one filesystem, so it does not count other disks
  mounted under `/` (for example, a separate `/home`).
- `--max-depth=1` lists only the directories directly under `/`.
- `sort -h` puts the biggest last, so it is at the bottom of the output.

Run the same command again inside the biggest directory, and keep
drilling down until the directory is small enough to inspect by hand:

```sh
sudo du -xh --max-depth=1 /var | sort -h
sudo du -xh --max-depth=1 /var/lib | sort -h
```

If the total is much smaller than what `df` reports, stop here and read
[df says full but du doesn't add up](../df-full-du-does-not-add-up/)
before deleting anything: the missing space is probably deleted files
still held open, or files `du` could not read.

## 3. Find the biggest individual files

Once a directory looks suspicious, list its largest files directly:

```sh
sudo find /var -xdev -type f -printf '%s %p\n' 2>/dev/null | sort -nr | head -20
```

- `-xdev` keeps `find` on one filesystem, like `-x` does for `du`.
- `-printf '%s %p\n'` prints the size in bytes first, so `sort -nr`
  sorts largest first.
- `2>/dev/null` hides `Permission denied` errors for files you cannot
  read. If many errors are hidden, re-run with `sudo`; without it,
  `find` silently misses everything owned by other users or the system,
  and the biggest file in the list may not be the biggest file on disk.
- To show sizes in human-readable form instead, pipe through
  `numfmt --to=iec`:

```sh
sudo find /var -xdev -type f -printf '%s %p\n' 2>/dev/null | sort -nr | head -20 | numfmt --field=1 --to=iec
```

To find only files over a threshold, for example 100 MB, use `-size`:

```sh
sudo find / -xdev -type f -size +100M -printf '%s %p\n' 2>/dev/null | sort -nr
```

## 4. Explore interactively with ncdu

If you prefer to browse instead of running one command per level,
`ncdu` shows the same top-down view interactively and lets you drill
into directories with the arrow keys:

```sh
sudo ncdu -x /
```

- `-x` again keeps it on one filesystem.
- Press `d` on a selected file or directory to delete it, but only
  after you have confirmed what it is: `ncdu` deletes immediately and
  does not move things to a trash folder.
- If `ncdu` is not installed, install it from your distribution
  (`sudo apt install ncdu` on Ubuntu/Debian, `sudo dnf install ncdu`
  on Fedora) or use the `du` commands above instead.

## 5. What the results usually mean

| What you find | Likely cause | Next step |
| --- | --- | --- |
| One huge log in `/var/log` | A program logging without rotation | See [/var/log is full](../var-log-full/); truncate a live log, don't delete it. |
| `/var/cache/apt` or `/var/lib/docker` | Package or container caches | See [free up disk space on an Ubuntu server](../free-up-disk-space-ubuntu-server/) or [Docker disk space](../docker-disk-space/). |
| A file in `/tmp` or a home directory | Downloads, caches, or old project data | Check it is yours and unneeded before removing it. |
| Many small files, not a few big ones | Too many files, not too many bytes | Check `df -i`: if inodes are at 100%, read [no space left but df shows free space](../no-space-left-on-device-but-df-shows-free-space/). |

## 6. Before you delete anything

- Confirm the file's owner and age (`ls -lh <file>`). A large file
  owned by the system or by a running service is not automatically
  safe to remove.
- Never delete a file that is still open: deleting it frees nothing
  until the program closes it, and the program may recreate it. See
  [deleted files still using space](../deleted-files-still-using-space/).
- If you are unsure what a file is, leave it and ask: the space it
  uses is rarely worth breaking a service over.
