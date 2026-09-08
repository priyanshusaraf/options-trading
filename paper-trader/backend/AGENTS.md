# Backend work

- Run Python from this directory with `.venv/bin/python`.
- Run focused tests for the change. For a release candidate, run `.venv/bin/python -m pytest -q tests research_tests`.
- Use dummy values in subprocess environment mocks; never capture real credentials.
- For local runtime checks, use a mock provider, paper execution, disabled dotenv loading, no live acknowledgement and a temporary database.
- Preserve owner isolation, completed-bar behavior, strategy identity, ledger reconciliation and risk-reducing exits.
- Explain failures with stable reason codes and safe, useful messages.
- Check deployment effects when changing migrations, dependencies, configuration or providers.
