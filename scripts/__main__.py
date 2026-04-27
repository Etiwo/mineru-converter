"""Allow running as: python3 -m scripts.cli"""

import sys
from pathlib import Path

# Ensure the project root is in sys.path
_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from scripts.cli import main

sys.exit(main())
