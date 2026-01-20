"""
Brief: Validate FK coverage for mapped JSON outputs.

Inputs:
- --base-dir: directory containing step3 LLM outputs

Outputs:
- Logs missing files and FK issues to stdout/stderr

Usage (from project root):
- python -m mapping.scripts.validate_foreign_keys mapping/workflow_output/step3_llm
- python -m mapping.scripts.validate_foreign_keys --base-dir mapping/workflow_output/step3_llm
"""

from mapping.utils.validate_foreign_keys import main
from utils import setup_logger


if __name__ == "__main__":
    setup_logger()
    raise SystemExit(main())
