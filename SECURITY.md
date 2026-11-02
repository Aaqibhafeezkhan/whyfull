# Security

whyfull is usually run as root, so it is careful about what it does: it only reads files and runs a few read-only commands, and it never runs the fix commands it prints.

If you find a way to make whyfull change the system, execute something unexpected, or print a fix command that does more than it says, please report it privately through [GitHub's security advisory form](https://github.com/amlaban65/whyfull/security/advisories/new) rather than a public issue. You'll get a reply within a week.
