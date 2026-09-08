# Trading semantics comparison packet

## Scope

This packet compares the strongest local trading references against current Strategy OS risks:

- event and timestamp ordering;
- completed versus forming bars;
- cross-series alignment;
- deterministic replay;
- order and fill facts;
- partial fills and recovery;
- vector and streaming parity;
- dynamic Universe bias.

All local repository claims bind to the commits in repo-index.yaml.

## Comparison

| System | Strong pattern | Material weakness | Strategy OS decision |
| --- | --- | --- | --- |
| LEAN | Stable security identity, rich subscriptions, Universe → Alpha → Portfolio → Execution → Risk separation | Code-first strategy artifact and large engine | Primary reference for Universe, canonical identity, and portfolio-stage separation |
| NautilusTrader | One deterministic event-time architecture and explicit state reset | No durable graph artifact; event-driven research cost | Keep completed-bar V1 and one lowering; use its reset and time discipline |
| hftbacktest | Exchange and local timestamps, latency and queue models | Future tick domain, not V1 | Reserve timestamp and model identities for later tick work |
| Backtrader | Multi-data clock and derived minimum period | Host-language metaclass runtime, no immutable artifact | Keep cross-series and warmup lessons only |
| Freqtrade | Mature live, dry, backtest, pairlist, and order-operation history | Dynamic pairlists use current conditions or declare backtest bias; code-first identity | Treat current-pairlist backtests as explicit negative evidence |
| Hummingbot | Active, cached, and lost orders; client plus venue IDs; startup recovery | Crypto pair strings, several mutable state owners | Keep ambiguous-order and executor lifecycle patterns |
| vn.py | Separate outbound request, order update, and trade fill | Process-local event queue and composite strings | Keep fact separation and venue lowering |
| Lumibot | Option contracts, chains, assignment, exercise, and expiry | Mutable provider-shaped assets and weak provenance | Keep typed option lifecycle; reject provider dictionaries as authority |
| vectorbt | Fast whole-series component schema and named outputs | Hosted-use licence restriction; unversioned runtime classes; search inside components | Ideas only; keep search outside components |
| OpenAlgo | Broker breadth and strong operational lessons | Mutable visual control-flow graph, no graph backtest, AGPL | Behavior reference only |

## Event and time decisions

Strategy OS should retain:

- completed-bar default;
- next-bar open fills where the accepted backtest contract requires them;
- one candle-to-frame conversion path;
- prefix causality checks at every node;
- explicit event, completed, available, recorded, and knowledge times;
- exact timezone and session policy;
- separate observation and execution instruments;
- no silent forward fill.

V2 should add a versioned event envelope instead of widening the current candle replay JSON in place. The envelope should represent:

- market observation;
- Universe membership change;
- rank result;
- provider correction;
- market-rule change;
- Workflow transition;
- chart artifact revision;
- broker event.

## Dynamic Universe warning

Freqtrade's current PairListManager classifies handlers as backtest-safe, unsupported, no-action, or biased. Its official backtesting documentation states that dynamic pairlists can use current market conditions and may not reproduce historical membership. This confirms a Strategy OS rule:

> A Dynamic Universe backtest is valid only when every selection input and membership change is point-in-time and replayable.

The V2 Universe engine must store:

- exact Universe definition version;
- evaluation time and knowledge cutoff;
- candidate population before filters;
- every filter result;
- rank score and frozen tie-break;
- top-K selection;
- enter, leave, cooldown, and hysteresis decisions;
- provider and dataset authority;
- historical listing and delisting eligibility.

## Order and fill decisions

Keep these facts separate:

    strategy decision
    candidate intent
    portfolio admission
    capital reservation
    execution command
    broker acknowledgement
    order update
    fill
    position
    accounting
    reconciliation

Current Strategy OS already separates execution intent and immutable order events. The missing durable facts are portfolio admission and capital reservation.

## Strong patterns to adopt

1. LEAN: Universe selection does not own portfolio construction.
2. Hummingbot: terminal-looking orders remain reconcilable when late fills remain possible.
3. vn.py: broker requests, order states, and fills use separate types.
4. NautilusTrader: time and state reset are runtime dependencies.
5. Backtrader: nested warmup derives from dependencies.
6. Freqtrade: declare when current selection makes a historical result biased.
7. Lumibot: option expiry, assignment, exercise, and settlement are domain events.

## Patterns to reject

- current ticker lists as historical Universe truth;
- provider pair strings as canonical identity;
- a single mutable order row as command, acknowledgement, and fill;
- a matching API shape presented as research/live parity;
- a vector result trusted without prefix causality;
- a connected socket presented as fresh market data;
- passive-fill claims without queue and latency model identity;
- strategy code that reads provider APIs directly.

## Candidate golden tests

1. Cross-instrument strategy observes NIFTY and INDIA VIX, trades a different target, and never reads a future bar.
2. One instrument has a missing bar while another advances.
3. Higher-timeframe input uses only the last completed bar.
4. A listing starts after the backtest window begins.
5. A symbol changes while canonical identity remains stable.
6. A Universe member leaves while an open position remains subscribed and manageable.
7. A provider correction invalidates a cached result.
8. A partial fill arrives after an order appears cancelled.
9. Cancel and fill cross in either order.
10. A process dies after broker submission but before local acknowledgement.
11. Two valid candidate intents compete for one fundable amount.
12. An atomic basket cannot be fully funded.
13. A dynamic selector changes after entry while held identity stays fixed.
14. Replay and vector evaluation produce the same first divergent event or no divergence.
15. Cost, fee, and rounding rules reproduce exact final money values.

## Verdict

KEEP + HARDEN the Strategy OS trading foundation.

Smallest safe next slice: v1-portfolio-admission-reservation.
