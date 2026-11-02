---
title: df says the disk is full but du doesn't add up
description: df reports a full disk while du finds far less. Here are the five reasons the numbers disagree on Linux, and the commands to find and free the missing space.
short: Find the space that df counts but du can't see.
---

You run `df -h` and the root filesystem is at 100%. You run `du -sh /*` to see where it went, and the totals come to a fraction of that. Both tools are right: they measure different things. `df` asks the filesystem how many blocks are in use. `du` walks the directory tree and adds up the files it can reach. Anything using blocks that isn't reachable by walking the tree shows up in `df` and not in `du`.

There are five usual reasons, roughly in order of how often they're the answer.

## 1. Deleted files that a process still has open

This is the most common one by far. A log file gets deleted with `rm` while the service writing to it is still running. The name disappears, so `du` can't see it, but the data stays on disk until the last process holding the file closes it.

List them with `lsof`:

```sh
sudo lsof +L1
```

`+L1` shows open files with a link count below 1, which means deleted. The `SIZE/OFF` column is how much space each one holds. If `lsof` isn't installed, `/proc` has the same information:

```sh
sudo find /proc/*/fd -ls 2>/dev/null | grep '(deleted)'
```

Restarting the service that holds the file frees the space. If you can't restart it right now, empty the file through `/proc` instead, using the PID and file descriptor number from the output above:

```sh
sudo truncate -s 0 /proc/1234/fd/7
```

There's a [full guide to deleted-but-open files](../deleted-files-still-using-space/) if you want the details.

## 2. Files hidden under a mount point

If something wrote files into a directory such as `/data` before a disk was mounted there, those files still use space on the root filesystem. Once the other disk is mounted over the directory, they're hidden: `du` sees the mounted disk's contents instead.

Bind-mount the root filesystem somewhere else to see underneath the mounts:

```sh
sudo mkdir -p /mnt/rootfs
sudo mount --bind / /mnt/rootfs
sudo du -sh /mnt/rootfs/data /mnt/rootfs/home /mnt/rootfs/var
sudo umount /mnt/rootfs
```

Any mount point that shows a large size here has files hiding under it. Move or delete them through `/mnt/rootfs`, then unmount.

## 3. du couldn't read everything

Run as a normal user, `du` skips directories it isn't allowed to read and prints "Permission denied" for each one. Those are often exactly the directories that hold the space: `/var/lib/docker`, database directories, other users' home directories. Run it with `sudo`, and stay on one filesystem with `-x` so the totals compare with `df`:

```sh
sudo du -xh --max-depth=2 / 2>/dev/null | sort -h | tail -20
```

## 4. Space reserved for root

ext4 keeps about 5% of its blocks for root by default. `df` leaves them out of the "Avail" column, so a filesystem can show 0 bytes available while `du` adds up to only 95% of the size. Programs running as other users get "No space left on device", while root can still write.

```sh
sudo tune2fs -l /dev/sda1 | grep -i 'reserved block count'
```

On a system disk, keep the reserve: it's what lets root log in and clean up. On a disk that only holds data, lowering it to 1% with `sudo tune2fs -m 1 /dev/sdb1` is common.

## 5. Snapshots and copy-on-write filesystems

On btrfs and ZFS, snapshots keep the blocks of files that have since been deleted or changed. `du` sees the current files, while `df` counts everything the snapshots still reference.

```sh
sudo btrfs subvolume list -s /     # btrfs snapshots
zfs list -t snapshot -o name,used -s used   # ZFS snapshots, largest last
```

Tools like Snapper and Timeshift create snapshots automatically, so check their settings if you find dozens of them.

## A smaller reason: sparse files and apparent size

`ls -l` and `du --apparent-size` report how long a file is, while plain `du` reports the blocks it uses. Sparse files, such as `/var/log/lastlog` or VM disk images, can look huge in `ls` and use almost nothing. This makes `ls` disagree with `df`, not `du`, but it's worth knowing when the numbers look strange.
