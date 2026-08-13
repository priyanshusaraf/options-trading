# Backend execution rules

Run commands from this directory. `python` is not a supported launcher; use `.venv/bin/python`. macOS has no `timeout` command.

Before editing, inspect the active capsule and the existing dirty diff. Files listed as protected in the capsule are inherited and immutable for that task, even when already modified.

Use focused tests during implementation, then the affected backend or research subsystem. Run both broad suites only at the phase gate:

```bash
.venv/bin/python -m pytest -q tests research_tests
```

Bare `pytest` can omit `research_tests`. Quiet output with exit 0 may be normal; keep the exit code and full log. Query migration heads from the migration tools rather than copying a number from documentation.

For long commands use the repository logged runner and write under the active assignment:

```bash
.venv/bin/python ../../.codex/scripts/run_logged.py \
  --task TASK --assignment ASSIGNMENT --label LABEL --cwd "$PWD" -- COMMAND
```

Never start the app from the shipped environment. Runtime verification must use the safe-runtime skill: mock provider, paper execution, disabled dotenv, empty live acknowledgement, and a unique temporary database. Do not access live credentials, arm execution, deploy, or contact the live VPS.

Preserve causal completed-bar behavior, owner scoping, exact admission and implementation identity, paper/live separation, ledger reconciliation, and risk-reducing exits. A backend change stops at the frontend API/design boundary unless the owner explicitly opens the frontend gate.
