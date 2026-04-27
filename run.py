#!/usr/bin/env python3
"""Entry point for mineru-converter-skill."""

import sys
from pathlib import Path

# Ensure project root is in path
project_root = Path(__file__).resolve().parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from scripts.cli import main

sys.exit(main())
