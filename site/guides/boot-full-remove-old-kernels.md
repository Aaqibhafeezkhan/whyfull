---
title: /boot is full? Remove old kernels on Ubuntu, Debian, Fedora and RHEL
description: Free space in /boot and / by removing old kernels safely with apt, dnf or zypper, including what to do when apt itself fails because /boot is full.
short: Remove old kernels with your package manager.
---

Every kernel update installs a new kernel next to the old ones. Each kernel uses space in `/boot` (the kernel image and initramfs) and in `/lib/modules`, often 300 MB or more in total. When `/boot` is a small separate partition, a few updates are enough to fill it, and then the next update fails.

Remove old kernels with the package manager, never by deleting files from `/boot` by hand. That leaves the package database pointing at files that don't exist.

## First, see what you're running

```sh
uname -r
```

Keep the running kernel and the newest installed one. Everything older can usually go.

## Ubuntu and Debian

List installed kernels:

```sh
dpkg --list 'linux-image-*' | grep '^ii'
```

Remove the ones apt considers unused:

```sh
sudo apt autoremove --purge
```

If old kernels are still listed afterwards, they were installed manually. Purge them by name, for example:

```sh
sudo apt purge linux-image-6.8.0-31-generic linux-modules-6.8.0-31-generic
```

**When apt fails because /boot is already full:** apt can't finish anything until it has room, including the removal. Purge the oldest kernel directly with `dpkg`, then let apt fix the rest:

```sh
sudo dpkg --purge linux-image-6.8.0-31-generic
sudo apt --fix-broken install
sudo apt autoremove --purge
```

## Fedora, RHEL, Rocky and AlmaLinux

dnf keeps a set number of kernels (`installonly_limit`, 3 by default). Remove all but the newest ones:

```sh
sudo dnf remove --oldinstallonly
```

To keep fewer from now on, set `installonly_limit=2` in `/etc/dnf/dnf.conf`.

## openSUSE

```sh
sudo zypper purge-kernels
```

Which kernels it keeps is set by `multiversion.kernels` in `/etc/zypp/zypp.conf`.

## Arch Linux

Arch replaces the kernel on each update rather than keeping old versions, so old kernels don't pile up. If `/boot` is full there, look for extra kernels you installed (`linux-lts`, `linux-zen`) or leftover fallback images.
