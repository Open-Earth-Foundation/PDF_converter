"""
Brief: Run LLM-assisted FK mapping against extraction outputs.

Inputs:
- --input-dir: directory with extraction JSON
- --output-dir: destination directory for mapped JSON
- --model: override mapping model (defaults to llm_config.yml mapping.model)
- --apply: write mapped files (default: dry-run)
- --retry-on-issues: re-run LLM mapping for FK/duplicate issues using feedback
- --retry-rounds: max retry rounds (default: 1)
- --retry-max-duplicates: max duplicate groups to include in retry planning
- Env: OPENROUTER_API_KEY

Outputs:
- Mapped JSON files when --apply is set
- Logs to stdout/stderr

Usage (from project root):
- python -m mapping.scripts.apply_llm_mapping --apply
"""

from mapping.utils.apply_llm_mapping import main
from utils import setup_logger


if __name__ == "__main__":
    setup_logger()
    raise SystemExit(main())
