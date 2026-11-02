---
title: Docker using too much disk space
description: /var/lib/docker filling your disk? See what Docker is using with docker system df, then clean build cache, images, containers, volumes and container logs safely, and stop them growing back.
short: Clean /var/lib/docker without breaking anything.
---

Docker keeps everything under `/var/lib/docker`: images, the writable layers of containers, volumes, build cache and container logs. On a busy build server or a host that has been running containers for months, this is often the single biggest directory on the disk.

The one rule: **never delete files in `/var/lib/docker` by hand.** Removing things from `overlay2` directly corrupts images and containers in ways that are hard to recover from. Docker has a cleanup command for each kind of data, so use those.

## See what's using the space

```sh
docker system df
```

```text
TYPE            TOTAL     ACTIVE    SIZE      RECLAIMABLE
Images          41        6         18.2GB    15.9GB (87%)
Containers      9         6         412MB     3MB (0%)
Local Volumes   12        4         6.1GB     2.4GB (39%)
Build Cache     310       0         9.8GB     9.8GB
```

The `RECLAIMABLE` column is what the prune commands below can free. `docker system df -v` breaks it down per image, container and volume.

`docker system df` doesn't count container logs. Check those separately:

```sh
sudo du -h /var/lib/docker/containers/*/*-json.log | sort -h | tail
```

## Clean up, safest first

**Build cache.** Layers kept to make later `docker build` runs faster. Nothing breaks without them: the next build is just slower.

```sh
docker builder prune -f          # unused cache
docker builder prune -a -f       # all of it
```

**Stopped containers.** Check that you don't need anything inside them first.

```sh
docker container prune -f
```

**Unused images.** `-a` removes every image that no container is using, not just untagged ones. They're downloaded again when something needs them.

```sh
docker image prune -a -f
```

**Volumes.** Volumes hold real data such as databases, so look before you prune. Since Docker Engine 23, `docker volume prune` only removes anonymous volumes. Add `-a` to include named volumes that no container is using.

```sh
docker volume ls -f dangling=true
docker volume prune -f
```

`docker system prune` does several of these in one go. Read what it lists before you confirm.

## Container logs

With the default `json-file` log driver, Docker keeps everything a container prints, forever. A chatty container can write tens of gigabytes. To empty one container's log without stopping it:

```sh
sudo truncate -s 0 "$(docker inspect --format '{{.LogPath}}' my-container)"
```

To cap logs for good, add this to `/etc/docker/daemon.json` and restart Docker:

```json
{
  "log-driver": "json-file",
  "log-opts": { "max-size": "50m", "max-file": "3" }
}
```

```sh
sudo systemctl restart docker
```

The limits only apply to containers created after the change, so recreate long-running containers to pick them up.

## Move Docker to a bigger disk

If the root filesystem is simply too small, point Docker at another disk with `"data-root": "/srv/docker"` in `daemon.json`. Stop Docker, copy `/var/lib/docker` to the new place with `rsync -aHAX`, then start it again.
