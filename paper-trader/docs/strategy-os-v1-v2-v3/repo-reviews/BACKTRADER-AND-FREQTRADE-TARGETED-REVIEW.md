# Backtrader and Freqtrade targeted review

Date: 22 August 2026

Purpose: close the two queued local-review gaps relevant to cross-instrument evaluation and Dynamic Universe architecture.

Both reviews are source-read. Neither repository was installed or run.

## Backtrader

Source:

- repository: mementum/backtrader;
- commit: b853d7c90b6721476eb5a5ea3135224e33db1f14;
- licence: GPL-3.0;
- verdict: REFERENCE ONLY.

Files inspected:

- backtrader/lineiterator.py;
- backtrader/cerebro.py;
- tests/test_ind_minperiod.py;
- samples/multidata-strategy/multidata-strategy-unaligned.py.

### Relevant abstractions

Backtrader represents data and indicators as line iterators with a first data source acting as the clock. It derives a minimum period from input data and child indicators. Cerebro aligns multiple feeds around the earliest current timestamp and delays feeds that are ahead.

### Strong patterns

- Cross-series evaluation needs one explicit time frontier.
- A derived indicator cannot become valid before its dependencies.
- Multi-data strategies may observe one series and trade another.
- Vector and step-by-step paths still need identical semantics.

### Weak patterns

- Runtime composition depends on Python metaclasses and object ownership.
- Graph, component version, dataset, and execution evidence are not one immutable artifact.
- Data alignment is host-runtime behavior rather than an explicit Strategy contract.

### Strategy OS decision

Keep:

- explicit aligned frontier;
- dependency-derived warmup;
- separate observation and traded target.

Reject:

- Backtrader as dependency;
- host-language objects as Strategy identity;
- implicit data alignment.

Concrete action:

- include unaligned cross-series fixtures in the reconstruction and causality test plans.

## Freqtrade

Source:

- repository: freqtrade/freqtrade;
- commit: 0a9b55dd83934d7d5086fcba150c1c36ab406661;
- licence: GPL-3.0;
- verdict: REFERENCE ONLY.

Files and evidence inspected:

- freqtrade/plugins/pairlistmanager.py;
- freqtrade/plugins/pairlist/IPairList.py;
- StaticPairList and representative dynamic filters;
- strategy/interface.py;
- data/dataprovider.py;
- persistence/trade_model.py;
- backtesting and pairlist tests;
- official backtesting documentation;
- current look-ahead issue reports.

### Relevant abstractions

PairListManager chains one generator and several filters. Each handler declares whether it supports backtesting:

- yes;
- no;
- no action;
- biased.

The manager warns when a dynamic handler uses current conditions or behaves differently in backtest. The official documentation says dynamic pairlists can rely on current market conditions and cannot guarantee reproducible results.

### Strong patterns

- A selection component declares its historical capability honestly.
- Generator and filters form explicit stages.
- Current whitelist and blacklist remain separate.
- Provider ticker requirements are declared.
- Reproducibility warnings are visible rather than hidden.

### Weak patterns

- Current conditions can define historical selection.
- Strategy identity remains source code and configuration.
- Pair strings are provider-market identifiers, not canonical economic identity.
- Dynamic selection, Strategy execution, and current bot state remain closely coupled.

### Strategy OS decision

Adopt:

- explicit historical-capability classification for every Universe component;
- staged generator and filters;
- refusal when historical inputs are absent;
- clear bias warnings.

Reject:

- current provider list as historical truth;
- current market ticker data in evidence-grade Universe replay;
- static-list export as proof of a dynamic historical policy;
- Freqtrade code reuse under GPL.

Concrete actions:

- every Universe component declares LIVE_ONLY, POINT_IN_TIME_REPLAYABLE, or UNSUPPORTED_HISTORY;
- a Dynamic Universe backtest refuses when any required component is not point-in-time replayable;
- UniverseEvaluation records the complete population and every stage.

## Combined conclusion

Backtrader shows the runtime work needed to keep multiple data sources aligned. Freqtrade shows the research failure that occurs when dynamic selection cannot be replayed historically.

Strategy OS already has stronger timestamp, identity, and market-truth foundations. V2 should build Universe evaluation on those foundations rather than adopting either host runtime.
