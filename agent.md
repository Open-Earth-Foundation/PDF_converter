# agent.md

## Purpose

This repository contains a single AI project. All contributions must optimize for:

* **Readability**: clear docs, clean structure, no dead/unused code, and logical separation of concerns.
* **Maintainability**: reusable utilities, configuration-driven behavior, proper logging, minimal duplication.
* **Consistency**: a similar “feel” across modules/scripts via shared patterns, formatting, and conventions.

---

## Repository rules

* **One repository per AI project**
* **No monorepo for all AI projects**
* **Do not split one AI project across multiple repos**

---

## Documentation requirements

### README.md must be up to date

Every repo must have a `README.md` with:

* Install instructions
* Run instructions (local + docker)
* Required environment variables (documented, not secrets)
* Common workflows (tests, lint/format)

### Runnable scripts must have a top-level docstring

Every script intended to be executed must include a **top-level docstring** describing:

* What the script does (brief)
* Inputs
* Outputs
* Usage examples

**Docstring template:**

```python
"""
Brief: <one-liner description>

Inputs:
- <list inputs, files, env vars, args>

Outputs:
- <files, stdout, DB writes, API responses, etc.>

Usage:
- python app/scripts/<script_name>.py --arg1 ... --arg2 ...
"""
```

---

## Code organization

### Separation of concerns is mandatory

* API calls go into a dedicated module (e.g. `services/`).
* Helpers go into `utils/` (global) or `modules/<module>/utils/` (module-local).
* Standalone runnable scripts go into `scripts/` (global) or `modules/<module>/scripts/` (module-local).
* Prompts go into `prompts/` (global) or `modules/<module>/prompts/` (module-local).
* Data structures (e.g. Pydantic models) should be centralized in `models.py` (global and/or module-level `models.py`).

### Folder placement must follow the hierarchy

Use this structure:

```markdown
project_root/
│
├── app/                        # Main application code
│   ├── main.py                 # Entry point for the app
│   ├── run.sh                  # Optional startup script
│   ├── utils/                  # Utility modules (global)
│   ├── services/               # API calls, DB connections, external integrations
│   ├── scripts/                # Standalone scripts (global)
│   ├── prompts/                # LLM prompts (global)
│   ├── models.py               # Global Pydantic models
│   │
│   └── modules/                # Core modules/features
│       └── <module_name>/      # e.g. plan_creator, prioritizer
│           ├── utils/          # Module-specific utilities
│           ├── services/       # Module-specific integrations (if needed)
│           ├── scripts/        # Module-specific scripts
│           ├── prompts/        # Module prompts
│           ├── module.py       # Module logic (or api.py, etc.)
│           └── models.py       # Module-level Pydantic models
│
├── k8s/                        # Kubernetes deployment files
│   └── deployment.yaml
│
├── .github/
│   └── workflows/
│
├── .gitignore
├── .dockerignore
├── Dockerfile
├── requirements.txt
├── requirements-dev.txt        # Dev-only heavy packages
├── README.md
├── LICENSE.md
├── .env
├── .env.example
```

---

## Standalone scripts rules

Any script that can be executed standalone must:

1. Live under `app/scripts/` or `app/modules/<module>/scripts/`
2. Have a top-level docstring (see template above)
3. Use `argparse` for inputs
4. Include a `__main__` entry point

**Minimum required pattern:**

```python
import argparse
import logging


logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    """Parse CLI args."""
    parser = argparse.ArgumentParser(description="Describe what this script does.")
    parser.add_argument("--example", required=True, help="Example argument.")
    return parser.parse_args()


def main() -> None:
    """Script entry point."""
    args = parse_args()
    logger.info("Starting script with args=%s", vars(args))
    # ... script logic ...


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
```

---

## Formatting

### Python: Black

* All Python code must be formatted with **Black**.
* Default Black behavior is expected (no custom style unless repo explicitly configures it).

**VSCode `settings.json` snippet:**

```json
{
  "editor.formatOnSave": true,
  "[python]": {
    "editor.defaultFormatter": "ms-python.black-formatter"
  },
  "[typescript]": {
    "editor.defaultFormatter": "esbenp.prettier-vscode"
  },
  "[javascript]": {
    "editor.defaultFormatter": "esbenp.prettier-vscode"
  },
  "[typescriptreact]": {
    "editor.defaultFormatter": "esbenp.prettier-vscode"
  }
}
```

**Reference info (internal context / original sources):**

```text
Black formatter extension:
https://marketplace.visualstudio.com/items?itemName=ms-python.black-formatter

Internal Slack reference (OpenEarthFoundation workspace):
https://openearthfoundation.slack.com/archives/C03P5FN36AG/p1719494098264839
```

---

## Maintainability rules

### Prefer reuse over duplication

* If logic is reusable, it belongs in `utils/` (global) or `modules/<module>/utils/` (local).
* Do not copy/paste functions across scripts.
* Import shared helpers instead.

### Logging (required)

* Use Python’s `logging` module (not `print`) for operational output.
* Log key steps and important parameters (avoid logging secrets).
* Errors should be logged with stack traces where helpful.

### Remove dead code

* No unused functions, no commented-out blocks, no “maybe later” code.
* If it’s not used and not needed now, delete it.

---

## Configuration and secrets

* **Secrets go only in `.env`** (API keys, tokens, credentials).
* Provide a `.env.example` that documents required env vars (without real secrets).
* Model/provider selection (e.g. model names) must be **configuration-driven**:

  * Model names should be set via env vars (or a config file that reads env vars).
* Prefer **one configuration module/file** that centralizes model/provider settings.
* Do not scatter configuration constants across multiple unrelated scripts.

---

## Testing

* Use **pytest** for tests.
* New features should include tests where practical.
* Bug fixes should include a regression test whenever feasible.

---

## Pull requests

### PR scope

* PRs are done on **ticket level**.
* Exceptions: pure data updates with no code changes (still notify the team).

### PR description template

Include:

* **Main purpose**: What does this PR do?
* **Major/breaking changes**: Any API changes, behavior changes, config changes?
* **Run instructions**: How to run locally + tests to verify

---

## CI/CD and deployment

* Each AI project should include a **Docker setup** and documented commands in `README.md`.

**Expected examples:**

```bash
docker build -t my-great-app .
docker run -it --rm -p 8000:8000 --env-file .env my-great-app
```

* Deployment target is typically **k8s on AWS EKS** if needed.
* Serverless (e.g. AWS Lambda) may be considered for AI features where appropriate.
* CI/CD must run pytest on PRs and merges.

---

## Agent working rules

When making changes:

* Keep changes minimal and scoped to the task.
* Respect the existing folder structure; move files if they’re in the wrong place.
* Update `README.md` if setup/run behavior changes.
* If you add a runnable script, ensure it follows the standalone script rules.
* If you add dependencies:

  * Update `requirements.txt` / `requirements-dev.txt` accordingly.
  * Prefer not adding new deps unless necessary.

---

## Quick checklist for contributions

* [ ] Code formatted with Black
* [ ] No duplication (helpers in utils where appropriate)
* [ ] Clear separation of concerns (services vs utils vs scripts)
* [ ] Runnable scripts: docstring + argparse + `__main__`
* [ ] README updated if run/install changed
* [ ] Logging used instead of print
* [ ] pytest coverage added/updated when feasible
* [ ] PR description includes purpose, breaking changes, run instructions
