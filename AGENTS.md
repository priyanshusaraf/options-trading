# Strategy OS

- Write in plain language. Lead with the result and report what was actually verified.
- Work in this checkout; the Desktop clone is frozen. Check the branch and existing changes before editing. Preserve other work.
- Follow the current assignment. Read nearby code, tests and relevant documentation. Reuse existing utilities and avoid unrelated cleanup.
- Complete authorized work through verification. Ask only when essential information or permission for a specific action is missing.
- Run checks appropriate to the change. Reuse existing test files. Investigate failures rather than repeating unchanged runs. Never weaken checks to pass.
- For changed functions, keep cyclomatic and cognitive complexity below 22, Halstead difficulty below 80, and CRAP below 10 for high-risk code or 25 otherwise. Check for surviving mutants, dead code and redundant code; report any unverified requirement.
- Preserve the user's model and reasoning choices.
- Keep strategy identity and research evidence consistent. Use completed-bar data, isolate owners, and separate data providers from execution brokers.
- Keep paper and live trading separate. Fail closed to live trading; preserve risk-reducing exits.
- Get explicit permission for live money, live credentials, VPS access, destructive actions and deployment. Deploy only through `paper-trader/scripts/deploy.sh`.
- Keep secrets and private conversations out of code, logs and committed documents. Keep Git hooks enabled.
