"""
Make `compass_scraper.*` and top-level `transform` packages importable in
tests without installing the project. Adds <repo>/compass_scraper and <repo>
to sys.path before any test module is collected.
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scraper"))
sys.path.insert(0, str(PROJECT_ROOT))
