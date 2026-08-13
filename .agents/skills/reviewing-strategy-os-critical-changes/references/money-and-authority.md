# Money and authority review

For execution, binding, orders, fills, positions, accounting, paper/live separation, or authority, verify:

1. Ledger reconciliation remains exact.
2. ARM blocks entries only; exits remain possible.
3. Paper and live books remain separate and resolve fail-closed to live.
4. Binding remains the single execution decision; requested assignment cannot substitute for resolved strategy.
5. Attribution reaches the money record; withdrawal removes only the signals the withdrawn authority authored.
6. Grants/regrants match exact content; live authoritative IR stays absent.
7. Engine code remains provenance-blind, and `Position` does not absorb order lifecycle state.

Paper-by-default is structural. Live requires `PT_EXECUTION=live`, `PT_LIVE_ACK=I_UNDERSTAND_REAL_MONEY`, `PT_PROVIDER=kite`, and a process-local ARM that resets at startup. Local verification clears the acknowledgement and never arms. Preserve loud reporting of foreign-book positions rather than adopting them.

Do not harden one signal into one order, one action into one `Position`, order lifecycle into the position row, or one intent into one leg. Read runtime configuration rows before reasoning from code defaults; owner-set values may intentionally differ. Never clear an override without the owner naming the key. Do not restore the removed `intraday_leverage` cap. A funds-read failure must size to zero, and removing an entry gate must never disable exits.

Require focused evidence capable of going red. Escalate to phase-tier checks for shared safety, runtime, or schema boundaries. State the owner gate if live authority, sizing, routing, risk, execution semantics, VPS, credentials, destructive operations, licence-sensitive adoption, or real-money decisions are in reach.
