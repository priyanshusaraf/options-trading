# Competitor map

Date: 22 August 2026

Closed products are assessed from current public product behavior and first-party documentation. Internal architecture is marked unknown unless the product publishes it.

## Market map

| Product | Classification | Main overlap | Strategy OS posture |
| --- | --- | --- | --- |
| AlgoTest | DIRECT COMPETITOR | Indian strategy creation, backtest, paper, live, options, broker connections | learn onboarding and deployment clarity; compete on evidence and semantic continuity |
| Tradetron | DIRECT COMPETITOR | no-code Strategy builder, backtest, grade, deploy | learn funnel and accessibility; reject opaque grades |
| Streak | DIRECT COMPETITOR | rule builder, scanner, backtest, deploy for Zerodha users | compete on depth, provider neutrality, and research evidence |
| QuantConnect | DIRECT GLOBAL REFERENCE | Universe, research, backtest, portfolio, execution | strongest architecture reference; Strategy OS differentiates on visual retail workflow and India depth |
| Composer | ADJACENT GLOBAL COMPETITOR | AI-assisted build, backtest, execute | learn simple authoring; reject opaque AI semantics |
| MetaTrader 5 | ADJACENT COMPETITOR | code, test, optimize, execute, global broker ecosystem | understand as V3 competitor and integration surface |
| Sensibull | SPECIALIST INPUT PROVIDER and ADJACENT COMPETITOR | options chain, OI, Strategy builder, payoff analysis | remain weaker at options visualization if needed; make data executable and evidenced |
| Screener | SPECIALIST INPUT PROVIDER | Indian fundamentals, custom screens, alerts | treat future fundamental screening as a Universe view |
| TradingView | SPECIALIST INPUT PROVIDER and DISTRIBUTION THREAT | charting, drawings, alerts, Pine, webhooks | integrate semantic inputs; do not rebuild charting |
| OpenAlgo | INFRASTRUCTURE REFERENCE and DISTRIBUTION THREAT | 30-plus broker API, self-hosting, external integration | preserve provider architecture; compete on research trust |
| Broker terminals | ADJACENT COMPETITOR | execution, chart, watchlist, account | do not clone; connect through capability contracts |

## Serious competitor cards

### AlgoTest

Observed:

- Its current [Signals AI documentation](https://docs.algotest.in/Signals-AI/) describes plain-language or canvas Strategy creation, chart preview, backtest, forward test, and live deployment.
- Its [Forward Test documentation](https://docs.algotest.in/Signals-AI/Signals-Deployment/Forward-Test/) treats paper trading as a distinct live-data step before real capital.
- Its [Backtesting documentation](https://docs.algotest.in/Signals-AI/Signals-Backtest/) separates signal timing from traded leg configuration and presents drawdown, yearly return, and trade statistics.

Target customer: Indian retail options and indicator traders who want one guided path.

Visible strengths:

- short path from idea to paper;
- options and broker breadth;
- clear paper-versus-live step;
- chart preview;
- plain language entry.

Visible limits:

- public documentation emphasizes conventional performance summaries;
- exact immutable research lineage and independent reconstruction are not established by the inspected pages.

Copyability:

- onboarding and chart preview: months;
- broker and options breadth: longer operational work;
- exact evidence and semantic continuity: requires deeper architecture.

Pricing: not assessed in this inspection.

### Tradetron

Observed:

- Its current [backtesting page](https://tradetron.tech/backtest) presents a builder-to-backtest-to-deploy path, net-cost results, interactive reports, Monte Carlo, and a grade.
- Its help content describes backtests over Strategy lists and underlyings.

Target customer: no-code traders who want hosted automation across strategies and markets.

Visible strengths:

- direct product funnel;
- familiar no-code framing;
- broad deployment positioning;
- cost-aware public messaging.

Visible limits:

- a grade risks hiding evidence even when detailed reports exist;
- closed-source semantics and reconstructibility are unknown.

Strategy OS response:

- never compete with another opaque score;
- make candidate selection, costs, assumptions, and rejections inspectable;
- preserve exact Strategy and evidence identity.

Pricing: not assessed.

### Streak

Observed:

- [Streak](https://streak.zerodha.com/) presents options and equity Strategy design, backtest, scanner, and deployment.
- Zerodha support describes Streak as a no-code way to create, backtest, and deploy technical strategies.

Target customer: Zerodha users who want rule-based automation without code.

Visible strengths:

- distribution through a major broker;
- simple mental model;
- scanning and technical rules.

Visible limits:

- broker-centered distribution;
- research depth, exact data identity, and reproducibility are not established by inspected public material.

Strategy OS response:

- remain provider-neutral;
- make cross-instrument research, bounded optimization, and evidence the reason to switch;
- do not enter a feature-count race.

Pricing: not assessed.

### QuantConnect

Observed:

- [Universe Selection](https://www.quantconnect.com/docs/v2/writing-algorithms/universes/key-concepts) separates static and dynamic asset selection and reports security changes to the algorithm.
- The [Algorithm Framework](https://www.quantconnect.com/docs/v1/algorithm-framework/overview) separates Universe Selection, Alpha, Portfolio Construction, Execution, and Risk.

Target customer: global technical quantitative developers and institutions.

Visible strengths:

- mature multi-asset engine;
- explicit Universe and portfolio stages;
- research and live domain continuity;
- extensive data and execution ecosystem.

Visible limits for Strategy OS's target:

- code-first workflow;
- broad platform complexity;
- less retail-friendly visual evidence and guided India-specific product path.

Strategy OS response:

- use LEAN as architecture reference;
- keep a visual, progressively disclosed product;
- retain point-in-time India depth and human-readable evidence.

### Composer

Observed:

- [Composer](https://www.composer.trade/) presents AI-assisted Strategy building, backtesting, and execution.
- Its help content shows natural language generating a Strategy structure before backtest.

Target customer: US retail users who want simplified systematic portfolios.

Visible strengths:

- low-friction authoring;
- clear build, backtest, execute message;
- approachable abstractions.

Visible risks:

- AI-generated meaning can become opaque;
- market and regulatory fit differs from India.

Strategy OS response:

- make AI optional and downstream of deterministic contracts;
- never let natural language bypass the typed graph or evidence.

### MetaTrader 5

Observed:

- [MetaTrader Strategy Testing](https://www.metatrader5.com/en/terminal/help/algotrading/testing) supports testing and optimization of Expert Advisors, multi-currency work, visual testing, and parallel agents.

Target customer: global traders and developers using broker-hosted desktop automation.

Visible strengths:

- broker ecosystem;
- mature code, test, optimize, and execute loop;
- global asset reach;
- local and remote compute agents.

Visible limits for current Strategy OS:

- code-first Expert Advisor model;
- evidence and cross-provider identity differ from Strategy OS's direction;
- not an India V1 requirement.

Strategy OS response:

- treat MT5 as a V3 competitor and possible external execution surface;
- do not build a connection before demand.

### TradingView

Observed:

- [TradingView alerts](https://www.tradingview.com/support/solutions/43000595315-how-to-set-up-alerts/) can notify through a webhook.
- [Technical alerts](https://www.tradingview.com/support/solutions/43000763315-getting-started-with-technical-alerts/) cover indicators, Strategies, drawing tools, channels, rectangles, Anchored VWAP, and Fibonacci tools.
- Strategy alerts run a server-side copy whose settings remain independent from later chart edits.

Target customer: broad chart-first retail and professional traders.

Visible strengths:

- chart interaction;
- drawing vocabulary;
- alert distribution;
- Pine ecosystem.

Strategy OS response:

- integrate external signals through authenticated typed ingress;
- model chart artifacts as immutable Strategy dependencies;
- keep vendor rendering outside core semantics;
- do not clone TradingView.

### Sensibull

Observed:

- [Sensibull](https://sensibull.com/) presents options Strategy building, advanced option chain, OI analysis, and draft portfolios.

Classification: specialist options product and adjacent competitor.

Strategy OS response:

- consume or reproduce only data and interactions that support the Strategy workflow;
- keep OI and option-chain facts machine-readable as well as visual;
- do not compete on specialist breadth before V2 demand.

### Screener

Observed:

- [Screener features](https://www.screener.in/features/) include Indian company data, custom screens, custom ratios, filings, Excel export, and automatic alerts.

Classification: specialist fundamental input provider.

Strategy OS response:

- make future fundamentals point-in-time Strategy inputs;
- make the screener a view of the same Universe evaluation;
- do not build a disconnected fundamental portal.

### OpenAlgo

Observed:

- [OpenAlgo documentation](https://docs.openalgo.in/) presents a self-hosted common API across 30-plus Indian brokers and many external tools.

Visible strengths:

- broker breadth;
- self-hosting;
- interoperability;
- external automation surface.

Known local source findings:

- AGPL-3.0;
- strong broker adapter discipline;
- mutable visual control-flow graph;
- no exact graph backtest in the inspected commit;
- single-user runtime assumptions.

Strategy OS response:

- use behavior and failure lessons only;
- copy no code;
- compete on research validity, content identity, and end-to-end evidence.

## Competitive position

Strategy OS should not claim specialist superiority.

Its coherent position is:

    discover
    → formalize
    → research
    → validate
    → admit
    → deploy
    → execute
    → explain
    → review

The defensible part is the exact continuity of:

- Strategy;
- Universe;
- data;
- evidence;
- approval;
- portfolio admission;
- deployment;
- execution;
- review.

## Information limits

- Pricing was not collected systematically.
- Closed-source internal architecture is unknown.
- Customer counts, revenue, retention, and release velocity were not verified.
- Copy-time estimates in the moat analysis are planning judgments.
