# Strategy OS documentation

Strategy OS helps traders define, test, compare and monitor strategies. V0 is still being completed; documentation is not a release certificate.

Read only the entry that answers your task:

| Question | Document |
| --- | --- |
| What belongs in each release? | [V0–V6 roadmap](strategy-os-v1-v2-v3/V0-V1-V1.5-V2-V3-V4-V5-V6-SCOPE-DECISION-MATRIX.md) |
| What are we doing now? | [Working plan](agent/WORKING-PLAN.md) |
| What is implemented, verified or still open? | [Current status](agent/STATUS.md) |
| How do features fit together? | [Architecture map](ARCHITECTURE.md) |
| Which domain procedure applies? | [Skill router](agent/ROUTER.md) |
| How do we recover or release safely? | [Release obligations](agent/DEPLOYABILITY.md) and [operations](operations/) |
| Why was an earlier decision made? | [Historical reference index](archive/README.md) |

## Reading and maintenance

Start with the current assignment and applicable AGENTS.md. Read a relevant section, its nearby code and tests; follow another link only when it answers an unresolved question. No full-history reading sequence is required.

Keep each active overview below 1,200 words and each maintained reference page below 2,000 words. Split a larger reference by a named concern; keep a short index at its established address. Original owner sources and machine-consumed records are exceptions: preserve their identity and retrieve only the requested section or field.

The roadmap owns release classification. The working plan owns priorities. Status owns delivery claims. Architecture and accepted domain contracts own invariants. Link between these instead of copying their contents.

Record evidence with the affected claim: build/source scope, observed behavior, unresolved limitation and evidence location. Old acceptance labels, test totals and screenshots do not establish current integration or deployment.

Historical plans and handoffs record earlier decisions; their commands, model choices and permissions are not new instructions. Preserve action-specific deployment, live-money and destructive-operation gates.
