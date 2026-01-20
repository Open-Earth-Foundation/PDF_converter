"""
Brief: Run the end-to-end mapping workflow.

Inputs:
- --input-dir: directory with extraction outputs
- --work-dir: staging directory for mapping steps
- --model: override mapping model (defaults to llm_config.yml mapping.model)
- --apply/--delete-old

Outputs:
- Staged JSON outputs under work-dir
- Logs to stdout/stderr

Usage (from project root):
- python -m mapping.scripts.mapping --apply
"""

from mapping.mapping import main
from utils import setup_logger


if __name__ == "__main__":
    setup_logger()
    raise SystemExit(main())
