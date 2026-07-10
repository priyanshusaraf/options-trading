# Making a solo autonomous options/equity-intraday platform genuinely excellent — a decision-ready review

**Scope note on evidence quality.** This pipeline surfaced only 4 verified claims, and every one carried a strong, well-reasoned applicability dissent specific to your setup. Most of the statistically-flavored claims (Deflated Sharpe magnitudes, walk-forward-guarantees, the "25% cost drag," NSE price-band mechanics, SEBI feature lists) were **killed** in verification — usually because they were true in the abstract but wrong or inapplicable to a ₹22.5k solo 1-lot options bot that backtests underlyings. I have not smuggled killed claims back in. Where a recommendation rests on my own domain knowledge rather than a verified citation, I mark it **(evidence thin)** and you should treat it as a hypothesis to test, not a finding.

---

## 1. Executive summary — five highest-leverage moves

1. **Fix the instrument-mismatch in validation before anything else.** You backtest the *underlying* but trade *options*; no backtesting-methodology upgrade (walk-forward, DSR, stability scoring) closes that gap. This is the single biggest hole in your edge story. **HIGH.**
2. **Adopt out-of-sample discipline sized to your data, not institutional recipes:** select parameters by neighborhood stability, not peak Sharpe [2], and treat multi-market/multi-timeframe sweeps as *validation breadth*, not as 1,000 independent trials to Bonferroni-correct [1]. **MEDIUM.**
3. **Treat execution friction (spread + slippage on options) as your dominant cost, not brokerage.** Model it explicitly per-strike and gate entries on it. Your existing OI≥500 / spread≤3% picker is the right lever; tighten it. **HIGH (evidence thin on exact numbers).**
4. **Harden the live path you have never actually fired** — the first real order is its own first test. Reconcile the book to zero phantom rows before flipping to live; the risk loop flattens positions regardless of ARM state. **HIGH.**
5. **Prove edge on a verified, net-of-charges live track record before touching monetization.** In India, the compliant path to trading others' money is regulated (PMS/RIA/AIF), not a side effect of a good backtest. **MEDIUM (regulatory specifics: evidence thin — verify with primary SEBI sources).**

---

## 2. Trading edge: what the evidence actually supports

### Your current approach, judged honestly
Long-premium trend-following (buy CE/PE at delta≈0.50, −35% stop / +60% target, ratcheting trail) has two structural headwinds that no verified claim rebuts and that you must design around:

- **Theta and path-dependence.** A +60% premium target on a delta-0.50 option is achievable but time-sensitive; the same underlying move that would have paid off can be eaten by decay if the move is slow. This was the core of the dissent against transplanting FX trend-following results to options [2] — FX has linear payoffs, your instrument does not. **The −35%/+60% asymmetry is only favorable if your win rate × path-speed clears theta**, which you cannot confirm from an underlying-only backtest.
- **The validation gap is the real problem, not parameter tuning.** Multiple killed walk-forward claims and the dissents on [1] and [2] converge on the same point: optimizing *how* you pick EMA/z parameters is low-ROI when your backtest instrument (spot) differs from your traded instrument (option premium). Fix the measurement before refining the method.

### Validation methodology to adopt (ranked by leverage)

1. **Close the spot-vs-option gap.** Options history is genuinely unavailable to you, so do one of:
   - **Reconstruct synthetic option P&L** from your spot backtest using your own Black-Scholes engine (`options/pricing.py`) — price the delta-0.50 contract at entry and exit with modeled IV and theta, net of your charges. This turns a spot signal test into an approximate *premium* test. It is imperfect (IV path is assumed) but strictly closer to reality than spot returns. **HIGH-leverage, evidence thin on fidelity — validate the synthetic model against a few weeks of your own live paper fills.**
   - **Log live paper fills as your real out-of-sample set.** You already run paper execution; that stream *is* option-level ground truth. Accumulate 50+ signal-to-exit records per instrument before trusting any per-instrument edge (your MEMORY already flags "need 6+ months / 50+ signal history").

2. **Select parameters by stability, not peak Sharpe.** On whatever training data you do have, prefer parameter neighborhoods where nearby settings perform similarly, rather than the single best-Sharpe cell [2]. **MEDIUM** — the claim survived but its dissent is important: with only ~20–50 trades/instrument/year you lack the sample to identify "stable neighborhoods" rigorously, so use this as a tie-breaker and a guard against obvious overfits, not as a precise optimizer.

3. **Do not over-correct for multiple testing — but do not ignore it.** The False Strategy Theorem is real: as you test more variants N, the Sharpe bar for significance rises [1]. But the verified dissent is decisive for *your* workflow: you are running **one fixed rule across N market segments**, not mining N independent strategies on one dataset. That is closer to cross-market validation than to data-dredging, and Bonferroni-style penalties would *over*-penalize correlated instrument/timeframe cells. **Practical rule:** if you ever add a genuine parameter grid or several candidate strategies, apply a deflation penalty then; for the current single-rule sweep, the penalty is near-negligible and cross-market consistency is the more informative signal. **MEDIUM.**

4. **Where evidence is thin, say so.** There is *no* verified claim in this pipeline establishing that your specific EMA50+z-score rule has a durable edge. The SEBI "93% of F&O traders lose" framing was killed as non-applicable in its strong form, but the honest read is: **you have not yet demonstrated positive net-of-cost edge on your actual instrument.** Treat live paper results, not backtests, as the gate.

---

## 3. Execution & costs: concrete numbers and order-handling changes

### What the verified numbers actually say
- **Auto square-off penalty:** Zerodha charges **₹50 + 18% GST = ₹59 per squared-off order** [3]. On ₹22.5k that is ~0.26% per event. **But the verified dissent is critical and probably correct:** this fee applies to *dealer/call-and-trade* square-offs, and your bot force-closes intraday positions ~15 min before close via its own `square_off_intraday()`, so the broker mechanism should never fire. **Net: model it as a failure-mode cost (bot crash between 3:15–3:25), not a routine cost.** Keep your proactive close; that is what makes [3] inapplicable.
- **MIS auto square-off time moved 3:20→3:25 PM on 26 Dec 2025** [4]. Factually correct and current. Your architecture is insulated (you force-flat on a 15-min buffer off the 3:30 NSE close, ~3:15), so the change has **zero operational impact** — but confirm your buffer config still clears 3:25 with margin, and confirm F&O MIS timing separately if you ever route intraday futures.

### The cost that actually matters — and where evidence is thin
The **brokerage** figure is not your enemy (flat ₹20/order on NFO is ~0.4–0.6% round-trip on typical premiums). Your dominant, under-modeled cost is **bid-ask spread + slippage on the option leg**. The pipeline killed the "0.0082% Nifty-futures impact cost" claim precisely because it is a futures/institutional number irrelevant to 1-lot options — which means **you have no validated external benchmark for your true execution cost.** That is a gap, not a free pass.

**Concrete order-handling changes (evidence thin on exact thresholds — instrument these and measure your own realized slippage):**
1. **Log realized slippage on every paper/live fill** (intended mid-price vs actual fill) and build your *own* per-instrument, per-moneyness cost table. This is the single most valuable execution dataset you can create and nobody else can give it to you.
2. **Tighten the picker gate** beyond OI≥500 / spread≤3%. A 3% spread is a ~3% round-trip haircut before the trade even moves — on a +60% target that is survivable, but on marginal setups it is the difference between edge and noise. Consider spread≤1.5% for non-index underlyings.
3. **Prefer limit-with-marketable-offset over pure market orders** for entries to cap slippage, with a timeout-to-market fallback so you do not miss the signal. Fast candles + wide option spreads are where market orders bleed.
4. **Feed your measured slippage back into `charges.py`/backtest** so backtested equity reflects *your* execution, not an optimistic mid-fill assumption.

---

## 4. Platform engineering: reliability & backtest fidelity

### Reliability priorities (highest first)
1. **The live path has never fired a real order** (per your own CLAUDE.md). This is the top engineering risk. Before going live: run the full `LiveBroker`/`KiteOrderClient` path against a single 1-lot order in isolation, verify token refresh flows through `token_source` without restart, and confirm the circuit breaker and daily-loss halt actually trip in a forced test. **HIGH.**
2. **Reconcile the book to reality before flipping `PT_EXECUTION=live`.** Your risk loop marks and exits *regardless of ARM state* — phantom persisted rows become real flatten-orders on the live account. Clear/reconcile `positions` and `capital_state`. **HIGH.** (Your MEMORY already flags a stale backend PID as a recurring root cause — restart discipline is part of reliability, not a footnote.)
3. **Restart hygiene.** The disarm-on-start default is correct; the recurring stale-process incidents in your memory suggest you need a supervised process (launchd/systemd-style or `caffeinate` wrapper you already use) with a health heartbeat, so a hung signal loop is detected, not discovered days later.

### Backtest fidelity (highest-leverage fixes)
1. **Synthetic-option P&L layer** (see §2.1) — converts your spot sweep into an approximate premium sweep. Biggest fidelity gain available.
2. **Net-of-your-measured-slippage** rather than modeled charges alone (see §3). Your dry-run already enforces the cash ledger invariant to the paisa — extend that rigor to execution cost.
3. **Data lookback is a hard constraint** (Kite caps intraday-candle history; 3-year training windows are not constructible on 15m/30m — this was why the walk-forward claims were killed for you). **Design validation around 200-ish days of intraday history, not textbook 3y/1y windows.** Rolling shorter windows with stability scoring [2] is the realistic adaptation.

### Data vendors worth paying for — evidence thin
No verified claim covers vendor selection. From domain knowledge (treat as hypothesis): the thing you cannot get from Kite and that would most improve fidelity is **historical intraday options data** (premium + IV history) for the specific contracts you trade — vendors like GDFL/TrueData/Global Datafeeds sell NSE F&O historical tick/minute data for India. If a modest subscription gives you even 1–2 years of real option-premium history for your core underlyings, it directly closes the §2.1 gap with real data instead of synthetic reconstruction. **Verify current pricing/coverage yourself before buying — I have no verified source here.**

### Buy vs build
- **Keep building** your engine — it is tightly fit to your workflow and the OpenAlgo-comparison claims were killed (OpenAlgo *does* have offline/VectorBT backtesting, contrary to the killed claim, so "build because alternatives can't backtest" is a false premise). Switching platforms buys you little.
- **Buy** historical options data (above) rather than trying to reconstruct it perfectly. That is the one component where external data beats build-effort.

---

## 5. Regulation: SEBI/Zerodha for personal algo trading in 2026 — **evidence thin, verify against primary sources**

**Important honesty flag:** every SEBI-specifics claim in this pipeline was **killed** for misattribution or mischaracterization. So the following is my best reconstruction from general knowledge and the *reasoning inside the killed-claim verifications*, not verified findings. **Confirm each point against the actual SEBI circular (sebi.gov.in, "Safer participation of retail investors in Algorithmic trading," Feb 2025) and Zerodha's own compliance pages before relying on it.**

What the killed-claim analysis consistently indicated (directionally, unverified):
- SEBI's Feb 2025 retail-algo framework centers on **broker-mediated controls**: registration/exchange-approval of retail algos via your broker, a unique exchange-assigned **Algo-ID** for tagging orders, **static-IP whitelisting**, authentication, **kill-switch capability**, and order logging/monitoring. Compliance deadlines were reportedly **extended** (broker-compliance to ~Oct 1, 2025; fuller Algo-ID tagging pushed toward ~April 1, 2026). **These dates are unverified here — check them.**
- Crucially, several verifiers argued the **compliance burden sits primarily with the broker (Zerodha), not you as an individual trading your own capital through their API.** Position limits/concentration checks are broker/exchange-enforced, not features you must re-implement.

**Actions (low-regret regardless of exact rule text):**
1. **Confirm your API usage is registered/tagged per Zerodha's current algo policy.** If Zerodha requires you to register your Kite Connect app as an algo or attach an Algo-ID for automated order placement, do it before your first live order. **HIGH-priority action, MEDIUM confidence on the requirement.**
2. **You have already done the static-IP whitelist** (per your context) — that aligns with the framework's intent.
3. **Keep your audit trail** (you already have `trades`, `positions`, `capital_state`, snapshots, `signal_events`). Retaining timestamped order/decision logs is the one compliance-adjacent thing fully in your control and you already do it.
4. **Do not build speculative "SEBI compliance gates" into the engine** based on the killed claims — there is no verified requirement for retail-self-capital position-concentration modules. Spend that effort on the broker-registration step instead.

---

## 6. Capital & monetization path

### Sizing for ₹22.5k
- **You are capital-constrained to ~2–3 concurrent 1-lot positions** before margin/lot-cost binds (noted across multiple verifications). Accept this: it caps trade frequency, which in turn caps how fast you can accumulate the statistically-meaningful sample you need. **Do not lever up to fix this** — the dissents repeatedly warned that scaling position size breaks the very small-size assumptions (negligible market impact) that make a 1-lot bot viable.
- **Fixed 1-lot sizing is correct at this capital.** Your risk per trade on a −35% premium stop is bounded by premium paid; keep it that way until you have a verified live edge.
- **Watch the auto-square-off failure cost** (₹59/event [3]) only as a crash-mode tail, not a routine drag — your proactive close handles the normal case.

### Realistic growth expectations — evidence thin
There is **no verified claim** projecting returns for this strategy, and I will not invent one. What the evidence *does* support: (a) net-of-cost edge is unproven on your actual instrument (§2), and (b) execution friction on options is your dominant uncertainty (§3). **Honest expectation-setting: the near-term goal is not compounding ₹22.5k quickly — it is producing a clean, verified, net-of-charges live track record that proves positive edge exists at all.** Capital growth follows edge; it does not substitute for it.

### From a verified track record to legal monetization in India — **evidence thin, verify with SEBI primary sources**
No verified claim covers this; the following is general domain knowledge, flagged accordingly:
- **Trading your own capital → keeping the P&L is fully legal and unregulated as to others' money.** That is your current, correct monetization: your own returns.
- **Managing *other people's* money legally requires a regulated wrapper** — in India that typically means **SEBI registration as an Investment Adviser (RIA), a Portfolio Manager (PMS, which carries a high minimum-AUM/net-worth bar), or launching an AIF.** A good backtest or even a good live record does **not** by itself authorize taking client funds. **Verify current thresholds and category rules directly with SEBI before pursuing any of these.**
- **A verified, auditable, net-of-charges track record is the prerequisite input to all of those paths** — it is what an RIA registration, a PMS pitch, or an AIF LP conversation is built on. So the engineering you already have (paisa-accurate ledger, timestamped trades, equity snapshots) is exactly the asset that later unlocks the regulated route. Keep it clean and continuous.
- **Do not shortcut into "signal-selling" or unregistered advisory** — that is the area SEBI actively polices. The compliant sequence is: prove edge on own capital → build verified record → register under the appropriate SEBI category → then take external capital.

---

## Where verified claims conflict or are contested
- **[1] vs your workflow:** the False Strategy Theorem is verified, but its strongest dissent (that it targets N-independent-strategy mining, not your single-rule cross-market sweep) is, in my judgment, correct and should govern how you apply it — use cross-market consistency as signal, not heavy Sharpe deflation.
- **[3] verified fee vs applicability:** the ₹59 square-off fee is real but the dissent that it does not apply to API-managed positions that self-close early is persuasive; treat it as a tail cost only.
- **[2] verified method vs sample size:** stability scoring is sound, but your ~20–50 trades/instrument/year genuinely undercut its statistical power — use it as a guard, not a precise optimizer.
- **[4] verified fact, zero impact:** the 3:25 PM change is correct and confirmed but architecturally irrelevant to you.

## Biggest honest gaps in the evidence base
1. **No verified evidence your specific strategy has positive net edge** on options. Everything downstream depends on establishing this via live paper/real data.
2. **No verified option-execution-cost benchmark** for 1-lot retail — you must measure your own.
3. **SEBI/Zerodha specifics are unverified here** (all such claims were killed) — sections 5 and monetization must be confirmed against primary SEBI/Zerodha sources before you act on them.# CONFIRMED
- Multiple independent backtest trials (N > 1) increase the required SR₀ threshold via the False Strategy Theorem, making strategies statistically harder to validate: SR₀ rises with N, forcing observed SR to exceed a higher bar to achieve the same confidence level. Each added trial inflates the false-positive risk unless the observed SR substantially exceeds the threshold. [1/3 refutes] (Deflated Sharpe ratio — Wikipedia)
- In walk-forward validation of trend-following strategies, selecting parameters via 'neighborhood stability scoring' on training data alone—rather than optimizing for peak historical Sharpe ratio—yields more robust out-of-sample performance across rolling windows [1/3 refutes] (QuantInsti EPAT — FX Trend-Following: A Walk-Forward Validation Study)
- Zerodha charges ₹50 + 18% GST (₹59 total) per auto square-off event on each order squared off; on capital of ₹22,500 this represents ~0.26% slippage per triggered close. [1/3 refutes] (What are the auto square-off timings for open intraday positions? (Zerodha Support))
- Zerodha's Equity MIS auto square-off time was moved from 3:20 PM to 3:25 PM effective 26 Dec 2025. [1/3 refutes] (Changes to the auto square-off timings for Equity and F&O — Z-Connect by Zerodha)

# KILLED
- SEBI Algorithmic Trading Regulations (Feb 2025) require position limits, concentration checks, and audit trails for retail algo traders, but OpenAlgo has zero compliance features coded—no SEBI-specific validation rules, position concentration checks, or regulatory reporting format. The user's platform (CLAUDE.md) mentions SEBI 2025 framework is in force but contains no compliance gate logic.
  reasons: Two distinct problems with the claim.

1) Misattribution: CLAUDE.md (as provided) never mentions SEBI at all. The "SEBI's retail algo-trading framework (Feb 2025 circular, effective 2025) is in force" line lives in the separate "Context about the user and system" note appended to this conversation, not in CLAUDE.md itself. So "The user's platform (CLAUDE.md) mentions SEBI 2025 framework is in forc
- OpenAlgo provides NO offline backtesting engine—strategies must be validated live in Analyzer Mode sandbox (same gap as user's platform: option history unavailable, only underlying can be backtested via mock). This forces edge validation and position-sizing discovery to happen with real capital in live trading, not offline.
  reasons: Web verification directly contradicts the claim. OpenAlgo's documentation (docs.openalgo.in/skills/backtesting) describes a full offline backtesting engine: historical simulation across Indian/US/Crypto markets with market-specific transaction cost modeling, TA-Lib indicators, parameter optimization, walk-forward analysis, Monte Carlo robustness testing, and QuantStats tearsheets — plus "Historify
- Individual algorithmic traders incur losses overall despite using algorithmic strategies; algorithmic execution alone does not overcome negative edge or market structure disadvantages for retail traders.
  reasons: The claim is overstated and not directly supported by the source data retrieved. 

**What the source actually says:**
The Capitalmind article cites a SEBI study (FY22-FY24) showing that 93% of individual F&O traders lost money overall, with 99.3% trading options at least once. The article makes a statement: "individual traders who used algorithmic strategies also incurred losses overall."

**Criti
- Transaction costs consume approximately 25% of gross P&L, broken down as: 51% brokerage fees, 20% exchange fees, 29% government taxes. Any strategy must generate >25% edge just to breakeven net of costs.
  reasons: The claim is partially refuted on two grounds: (1) The source (Capitalmind, SEBI-registered analyst) does support the 25% cost figure and 51/20/29 breakdown, verifying the factual basis. (2) However, the prescriptive claim that "any strategy must generate >25% edge just to breakeven net of costs" is NOT stated in the source and is an unsupported extrapolation. The article says costs consume 25% of
- Deflated Sharpe Ratio framework requires adjusting observed Sharpe ratios downward by a penalty factor that grows with the number of independent backtests (N) conducted; for a trader testing 1,000+ strategy variants across instruments × intervals, this adjustment becomes substantial and operationalizes Bonferroni-style multiple-testing correction.
  reasons: The core mechanism is right — DSR does deflate the observed Sharpe by a factor that grows with the number of trials N (via the expected maximum Sharpe ratio under the null, incorporating skew/kurtosis and sample length) — so "penalty grows with N" and "1000+ variants → substantial adjustment" hold up. But the claim mischaracterizes the mechanism as "Bonferroni-style" and requiring "independent bac
- Overfitting probability scales non-linearly with the number of backtests attempted; if a trader tests 1,000 independent strategy variants, the best performer's Sharpe ratio is likely inflated by 50% or more in a material fraction of cases, making live performance unpredictable.
  reasons: The underlying mechanism (Sharpe inflation grows with number of independent trials tested; more trials require longer backtests to avoid false positives) is real and correctly attributed — it's the well-established finding of Bailey/Borwein/López de Prado/Zhu's "Pseudo-Mathematics and Financial Charlatanism" (2014) and the companion Deflated Sharpe Ratio paper. Search confirms the MinBTL framework
- The False Strategy Theorem proves optimal outcomes from backtests are right-unbounded (no upper limit): unlimited historical trials will always eventually find a winning strategy by pure chance. This directly implies: backtest sweep pipelines that test many strategies/timeframes/instruments without multiple-testing correction will report false positives proportional to N.
  reasons: The claim states false positives are "proportional to N," but the Wikipedia source it cites shows the threshold Sharpe ratio relationship is logarithmic-type (involving inverse normal quantiles), not linear. The formula ((1-γ)Φ⁻¹[1-1/N]+γΦ⁻¹[1-1/Ne]) demonstrates non-linear scaling, not proportionality. Additionally, the claim obscures that the theorem applies only when strategies are truly unskil
- Walk-forward validation using 3-year training periods with 1-year out-of-sample test windows, stepped forward incrementally, provides a rigorous test of parameter robustness across different market regimes and reduces overfitting risk
  reasons: The source (QuantInsti) is credible and accurately describes the 3-year/1-year walk-forward methodology on FX trend-following. However, the claim overgeneralizes: (1) The study validates the approach for FX, NOT options or equity intraday—asset classes with fundamentally different pricing dynamics (volatility smile, gamma, assignment). (2) The claim says the approach "reduces overfitting risk"—tru
- Walk-forward optimization directly reduces overfitting compared to simpler backtesting approaches, making out-of-sample performance a more reliable predictor of forward performance in live trading.
  reasons: The narrow factual claim (WFO reduces overfitting vs. single-split/naive backtesting by withholding test data from optimization) is accurate and matches the QuantInsti source and broader literature. But the claim as stated overreaches: it asserts WFO makes out-of-sample results 'a more reliable predictor of forward performance in live trading' — a much stronger, unsupported conclusion. Multiple so
- NSE automatically rejects or cancels limit orders placed beyond dynamically adjusted price bands when bands extend in the direction of price movement, leaving the opposite limit unchanged; e.g., stock at ₹100 with ₹90–₹110 band extends to ₹90–₹115 if upper limit is hit, and any sell/limit orders beyond ₹115 are rejected.
  reasons: The claim's central mechanic is wrong. NSE's actual sliding-price-band rule (circular NSE/FAOP/63405, effective Nov 18 2024, still in force) states that when the band flexes toward the direction of price movement, the OPPOSITE side band also shifts by the same amount so the whole band slides (keeping constant width) — this is explicitly designed to replace one-sided expansion. An independent sourc
- During volatility cooling-off periods for options, NSE imposes temporary asymmetric ceilings on call options and temporary floors on put options; new orders beyond these limits are rejected, but existing orders within the range remain active, creating a partial order-entry blackout during freak moves.
  reasons: The claim is based on a fintech blog (PayTM Money), a secondary source without citation to official NSE documentation. While the article's description of the mechanism was verified by WebFetch, it cannot be confirmed against NSE's primary authority sources (NSE website, official circulars, SEBI regulations) due to access limitations and lack of independent broker corroboration. For operational tra
- Equity intraday (MIS) positions auto square-off at exactly 3:25 PM IST; any open MIS position not manually closed by this time triggers automatic liquidation.
  reasons: The claim states "exactly 3:25 PM IST" but the cited Zerodha Support source explicitly notes that "Zerodha's risk management may modify these timings based on market volatility." The 3:25 PM time is correct but not always exact — it can be adjusted earlier during volatile markets. The core claim is factually supported (auto square-off does occur and liquidates open MIS positions), but the precisio
- To comply with Zerodha's equity intraday force-flat requirement, positions must be closed before 3:25 PM IST to allow the broker's auto square-off to trigger in time.
  reasons: The 3:25 PM figure itself is accurate and current: Zerodha revised equity-MIS auto square-off from 3:20 PM to 3:25 PM (F&O MIS to 3:26 PM) in a change effective late Dec 2025, still in force as of July 2026 (confirmed via Zerodha's own Z-Connect post and official X/tradingqna announcements). However, the claim's causal framing is backwards and thus refuted: 3:25 PM is not a deadline traders must b
- Nifty Futures has a measurable impact cost benchmark of 0.0082%, the correct India-specific metric for modeling real execution cost in backtests rather than assuming static bid-ask spread.
  reasons: The 0.0082% figure is genuinely in Zerodha Varsity's Nifty Futures chapter, but it's a single illustrative example (contrasted with MRF's ~0.3%) with no date/timestamp — not a maintained, current benchmark. More importantly, it's an impact-cost figure for the single most liquid Nifty Futures contract, not for options — the user's actual instrument (1-lot options at delta ~0.50 across a portfolio o
