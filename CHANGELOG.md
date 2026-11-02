# Changelog

## 0.1.0

First release.

- Checks: deleted-but-open files, Docker (build cache, images, containers, volumes, container logs), systemd journal, rotated and oversized logs, old kernels, package manager caches, snap revisions, core dumps, old temp files, user build and package caches, inode exhaustion, and the ext root reserve.
- Full-filesystem scan with a time limit, largest directories, crowded directories, and a warning when `df` and the files on disk don't add up.
- Text, JSON and Markdown output; `--fail-above` for cron and monitoring.
- Runs on Python 3.6+ with no dependencies; also shipped as a single `whyfull.pyz` file.
