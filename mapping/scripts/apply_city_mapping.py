"""
Brief: Apply a canonical cityId across extraction outputs.

Inputs:
- --input-dir: directory with cleaned extraction JSON
- --output-dir: destination directory for mapped JSON
- --apply: write mapped files (default: dry-run)

Outputs:
- Mapped JSON files when --apply is set
- Logs to stdout/stderr

Usage (from project root):
- python -m mapping.scripts.apply_city_mapping --apply
"""

from mapping.utils.apply_city_mapping import main
from utils import setup_logger


if __name__ == "__main__":
    setup_logger()
    raise SystemExit(main())
