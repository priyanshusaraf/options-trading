---
name: running-strategy-os-safely
description: "Start and verify a local Strategy OS runtime without touching live money, credentials, or production state. Use whenever browser or end-to-end behavior must be observed."
---

# Run Strategy OS safely

Never start a local process with the shipped environment. It can satisfy live gates and contend with the production system.

1. Use mock provider, paper execution, an empty live acknowledgement, dotenv disabled, and a unique temporary database.
2. Start backend and frontend separately, record their process IDs, and wait for the backend readiness response before driving a flow.
3. Confirm the runtime reports mock and paper state and remains unarmed. Treat any live state, credential use, or non-temporary database as a stop condition.
4. Drive only the intended flow; inspect behavior and logs. Stop both local processes and remove only the temporary database created for this run.
5. Never deploy, arm, modify live configuration, or access the live VPS from this workflow. Those actions require an owner gate.

Read [local runtime procedure](references/local-runtime.md) before starting. Read [browser evidence](references/browser-evidence.md) only for UI verification.
