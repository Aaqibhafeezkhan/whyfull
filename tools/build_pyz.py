#!/usr/bin/env python3
"""Build dist/whyfull.pyz, a single file that runs with any Python 3.6+.

    python3 tools/build_pyz.py
    python3 dist/whyfull.pyz --version
"""

import os
import shutil
import sys
import tempfile
import zipapp

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "..", "src", "whyfull")
OUT = os.path.join(HERE, "..", "dist", "whyfull.pyz")

MAIN = "import sys\nfrom whyfull.cli import main\nsys.exit(main())\n"


def main():
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    stage = tempfile.mkdtemp()
    try:
        shutil.copytree(SRC, os.path.join(stage, "whyfull"),
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        with open(os.path.join(stage, "__main__.py"), "w") as f:
            f.write(MAIN)
        zipapp.create_archive(stage, OUT, interpreter="/usr/bin/env python3", compressed=True)
    finally:
        shutil.rmtree(stage)
    print("wrote %s (%d KB)" % (os.path.relpath(OUT), os.path.getsize(OUT) // 1024))
    return 0


if __name__ == "__main__":
    sys.exit(main())
