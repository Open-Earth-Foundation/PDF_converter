"""
Brief: Clear hallucinated foreign keys in extraction outputs.

Inputs:
- --output-dir: directory containing extraction JSON outputs
- --apply: overwrite files in-place (default: dry-run)

Outputs:
- Updated JSON files when --apply is set
- Logs to stdout/stderr

Usage (from project root):
- python -m mapping.scripts.clear_foreign_keys --apply
"""

from mapping.utils.clear_foreign_keys import main
from utils import setup_logger


if __name__ == "__main__":
    setup_logger()
    raise SystemExit(main())
