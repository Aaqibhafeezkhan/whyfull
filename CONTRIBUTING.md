# Contributing to whyfull

Thanks for helping. Bug reports, new checks and better fix commands are all welcome.

## Setup

whyfull has no runtime dependencies. You only need Python 3 and pytest:

```sh
git clone https://github.com/amlaban65/whyfull
cd whyfull
python3 -m pip install pytest ruff
python3 -m pytest
python3 -m whyfull --help        # from the repo root, with PYTHONPATH=src
```

To see a realistic report without breaking your own machine, `tools/demo.py` builds a full "server" on a small loop disk. The instructions are at the top of the file.

## Adding a check

A check finds one specific, explainable use of disk space and says how to reclaim it. Here's a complete one:

```python
# src/whyfull/checks/flatpak.py
"""Unused Flatpak runtimes."""

from whyfull.checks import check
from whyfull.model import SAFE, Finding

MIN_BYTES = 200 * 10 ** 6
PATH = "/var/lib/flatpak/runtime"


@check("flatpak", "Unused Flatpak runtimes")
def run(ctx):
    if not ctx.system.exists(PATH) or not ctx.on_target(PATH):
        return
    size = ctx.size(PATH)
    if size < MIN_BYTES:
        return
    yield Finding(
        "flatpak", PATH, "Flatpak runtimes in %s" % PATH, size, SAFE, ctx.dev_of(PATH),
        detail="Runtimes no installed app needs any more. Flatpak downloads them again if needed.",
        fix=["flatpak uninstall --unused -y"],
    )
```

Then add `"flatpak"` to `MODULES` in `src/whyfull/checks/__init__.py`.

The rules that keep whyfull trustworthy:

1. **Never change the system.** Read files and run read-only commands only. The user runs the fix.
2. **Go through `ctx.system`** for every file read, `stat`, directory listing and command (`ctx.system.run([...])`). That's what lets tests point the check at a fake root.
3. **Only report what's on a target filesystem.** Use `ctx.on_target(path)`, and pass `ctx.dev_of(path)` as the finding's device.
4. **Report reclaimable bytes**, not the total, when they differ. For example, the journald check reports what vacuuming would free.
5. **Set a size floor** (`MIN_BYTES`) so the report stays about what matters. 100 to 200 MB is typical.
6. **Pick the risk honestly:**
   - `SAFE`: rebuilt automatically, like caches.
   - `REVIEW`: almost always fine, but worth a look.
   - `CAUTION`: can lose data or affect a running service.
   - `INFO`: no direct cleanup.
7. **Write fixes people can paste.** Use one command per line, and start a line with `#` for an explanation. Prefer the tool's own cleanup command (`docker builder prune`, `journalctl --vacuum-size`) over `rm`.
8. **Stay compatible with Python 3.6.** No f-strings, no walrus, no `capture_output=`. CI checks this.

## Tests

Tests build a fake root in a temp directory. `tests/conftest.py` has a `root` fixture with helpers to write files of a given size and age, fake command output, and fake `df` numbers:

```python
def test_flatpak(root, monkeypatch):
    monkeypatch.setattr(flatpak, "MIN_BYTES", 20000)
    root.write("/var/lib/flatpak/runtime/org.gnome.Platform/x", size=50000)
    f, = list(flatpak.run(make_ctx(root.system())))
    assert f.fix == ["flatpak uninstall --unused -y"]
```

Small files still take a 4 KB block on disk, so keep test floors well above that.

Run the checks CI runs before opening a PR:

```sh
python3 -m pytest
ruff check src tests tools
```

## Reporting a bug

Please include your distribution, the filesystem type (`df -T`), and the output of `sudo whyfull -v --format markdown`. Remove anything you don't want to share. If whyfull missed what was really filling your disk, say what it was: that's often the start of a new check.
