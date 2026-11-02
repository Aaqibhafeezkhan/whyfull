## What this changes

<!-- One or two sentences. For a new check: what fills the disk, and how the fix reclaims it. -->

## Checklist

- [ ] `python3 -m pytest` and `ruff check src tests tools` pass
- [ ] New or changed checks have a test using the fake root in `tests/conftest.py`
- [ ] whyfull still only reads: nothing here deletes, writes or restarts anything
- [ ] Fix commands are copy-pasteable and the risk level is honest
