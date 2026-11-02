---
title: "No space left on device" but df shows free space
description: Getting "No space left on device" when df says there's room? Check inodes with df -i, find the directories with millions of small files, and rule out the root reserve, inotify limits and btrfs metadata.
short: Out of inodes, the root reserve, or inotify.
---

The error says the disk is full, `df -h` says it isn't. That usually means the filesystem has run out of something other than bytes. Here are the causes in order of likelihood.

## Out of inodes

Every file and directory uses one inode, and ext4 creates a fixed number of them when the filesystem is made. A filesystem holding millions of tiny files can run out of inodes with plenty of bytes still free. Check with `df -i`:

```sh
df -i
```

```text
Filesystem      Inodes   IUsed IFree IUse% Mounted on
/dev/sda1      6553600 6553600     0  100% /
```

If `IUse%` is at or near 100%, that's the problem. Find which directories hold the most files:

```sh
sudo du --inodes -x / 2>/dev/null | sort -n | tail -20
```

The usual suspects:

- PHP session files in `/var/lib/php/sessions`
- A mail queue that never drains, in `/var/spool/postfix` or `/var/spool/exim`
- Cache directories of web applications
- Small files a cron job creates every minute and never removes

Deleting a directory with millions of files using `rm *` fails with "Argument list too long". Use `find` instead, which also lets you keep recent files:

```sh
sudo find /var/lib/php/sessions -type f -mmin +1440 -delete
```

The only way to get more inodes on ext4 is to recreate the filesystem with `mkfs.ext4 -N` or `-i`. XFS and btrfs allocate inodes as needed, so they rarely have this problem.

## The space reserved for root

ext4 keeps about 5% of the disk for root. `df` doesn't count it as available, but a regular user hitting the limit gets "No space left on device" while root can still write. If `df` shows a few percent free and the failing program runs as a normal user, this is likely it. The [df vs du guide](../df-full-du-does-not-add-up/#4-space-reserved-for-root) explains how to check and change it.

## Too many inotify watches

Programs that watch files for changes (`tail -f`, IDEs, `webpack`, file sync tools) can fail with "No space left on device" when the inotify watch limit is reached. It has nothing to do with disk space. Raise the limit:

```sh
cat /proc/sys/fs/inotify/max_user_watches
echo 'fs.inotify.max_user_watches=524288' | sudo tee /etc/sysctl.d/90-inotify.conf
sudo sysctl --system
```

## btrfs metadata full

btrfs keeps data and metadata in separate chunks. If metadata fills up, writes fail even with free data space. Check with:

```sh
sudo btrfs filesystem usage /
```

A balance of nearly empty data chunks usually frees room for metadata:

```sh
sudo btrfs balance start -dusage=10 /
```
