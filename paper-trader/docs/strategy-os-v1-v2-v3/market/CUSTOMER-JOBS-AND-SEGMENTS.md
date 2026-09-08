# Customer jobs and segments

## Evidence boundary

The Ultra prompt supplies one target profile:

- active trader;
- roughly 1.5 to 5 years of experience;
- understands charts and broker workflows;
- has real Strategy hypotheses;
- may use spreadsheets or light code;
- distrusts opaque claims;
- wants rigor without building infrastructure.

No customer interviews, usage telemetry, retention data, or willingness-to-pay study was provided or conducted in this static architecture slice. Every claim below is a product hypothesis until users confirm it.

## Primary jobs

### Formalize a trading idea

User statement:

    I can describe what I look for, but I need to turn it into exact repeatable logic.

Required product behavior:

- templates;
- visual graph;
- clear terms;
- cross-instrument inputs;
- no hidden broker semantics.

### Test whether the idea deserves trust

User statement:

    I need to know whether the result survives costs, other instruments, nearby parameters, and unseen data.

Required behavior:

- exact assumptions;
- baseline;
- bounded optimization;
- OOS;
- walk-forward;
- Monte Carlo;
- evidence rather than one score.

### Discover opportunities without staring at every chart

User statement:

    I want the system to find which instruments match my predeclared process today.

Required V2 behavior:

- point-in-time Universe;
- ranking and top-K;
- budget;
- why included and excluded;
- no current-list historical bias.

### Move from evidence to operation safely

User statement:

    I want paper, signal, or live as separate choices, with a clear refusal when something is unsafe.

Required behavior:

- exact deployment binding;
- provider capability;
- preflight;
- portfolio admission;
- ARM and kill;
- visible degradation;
- no silent substitution.

### Explain what happened

User statement:

    I need to know why the trade fired, why another did not, and whether the original thesis still holds.

Required behavior:

- why-trade and why-not-trade;
- immutable versions;
- first-divergence evidence;
- Workflow and candidate lineage;
- review.

## Experience layers

| Layer | Entry point | Needed controls | Avoid |
| --- | --- | --- | --- |
| Beginner systematic | template and static Universe preset | few parameters, guided research, paper deploy | empty canvas and infrastructure language |
| Intermediate | graph, research gates, chart input, Dynamic Universe preset | node editing, comparisons, Workflow template | hidden assumptions and magic score |
| Advanced | custom nodes, rankings, provider bindings, custom Workflow | exact contracts, Python path, exports, diagnostics | broker-specific core and opaque automation |

All layers use the same backend semantics.

## Workflow segments

### Research-only trader

Current stack:

- spreadsheet;
- chart platform;
- CSV;
- occasional Python notebook.

Switching reason:

- exact data and Strategy identity;
- bounded optimization;
- persistent evidence.

Refusal reason:

- broker prompts in a research product;
- data lock-in;
- private logic concerns.

### Signal user

Current stack:

- chart alerts;
- messaging;
- manual execution.

Switching reason:

- typed attributable signals;
- why and expiry;
- normal research and admission.

Refusal reason:

- latency ambiguity;
- unreliable notifications;
- forced broker connection.

### Paper-first operator

Current stack:

- broker paper product or spreadsheet.

Switching reason:

- same Strategy identity and semantics;
- provider state;
- operational evidence.

Refusal reason:

- paper behavior differs from live;
- unclear failure state.

### Controlled live trader

Current stack:

- broker terminal;
- custom script;
- no-code platform.

Switching reason:

- multi-provider separation;
- position ownership;
- reconciliation;
- risk and protection;
- evidence.

Refusal reason:

- credential trust;
- live outage risk;
- opaque execution or support access.

## Trust barriers

1. Backtest assumptions are hidden.
2. Data may contain look-ahead or survivorship bias.
3. Paper and live may differ.
4. Broker credentials may leak.
5. Support may see private logic.
6. Platform may silently change Strategy meaning.
7. Dynamic scanners may select historical winners with current data.
8. Optimization may overfit.
9. A connected screen may not mean fresh data.
10. The user may not understand why a trade was rejected.

## Research questions

Interview and observe:

- What tool starts the user's idea process?
- What causes them to abandon a backtest?
- Which assumptions do they inspect today?
- How do they decide a Strategy is ready for paper?
- How do they handle simultaneous opportunities?
- What broker and data combinations do they use?
- What proof would make them connect a broker?
- Which Strategy content do they consider private?
- Do they want signal-only?
- What does a useful why-not-trade explanation contain?
- Would they use Dynamic Universe daily?
- Which Workflow steps are repeated enough to template?
- What monthly price fits research-only, paper, and controlled-live value?

## Telemetry with consent

Safe aggregate events:

- time to first Strategy open;
- time to first backtest;
- validation methods opened;
- refusal categories;
- provider connection failure category;
- paper activation;
- return to an existing Strategy;
- node category search;
- Workflow template use;
- Dynamic Universe budget and completion class.

Avoid:

- raw graph;
- parameter values;
- custom code;
- instrument combination that reconstructs private logic;
- broker payload;
- dataset content.

## Distribution hypothesis

X may be useful because active traders discuss market questions publicly. Treat it as a test:

    impression
    → landing
    → signup
    → first Strategy
    → first backtest
    → paper
    → repeat use
    → paid

Do not optimize for clicks alone. Paid financial-product advertising requires a current legal and platform-policy check.
