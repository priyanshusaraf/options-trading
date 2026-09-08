# Task benchmark specification

> Timing amendment: T-19 Dynamic Universe inspection is now a V1 task. T-20 general Workflow progress remains V2.

Status: implementation-ready benchmark, not executed

## Test population

Recruit by experience and workflow, not age alone:

- 1.5 to 3 years active trading;
- 3 to 5 years active trading;
- spreadsheet or light-code users;
- discretionary, semi-systematic, and systematic users;
- at least one options-heavy and one equity-research-heavy cohort.

Do not ask participants to disclose private Strategy logic beyond what the task needs.

## Measures

For each task record:

- completion;
- completion time;
- wrong interpretation;
- number of hidden assumptions encountered;
- backtrack count;
- recovery time;
- confidence from 1 to 5;
- developer explanation required;
- refusal understood;
- evidence opened;
- accessibility blocker;
- desktop or mobile.

## Tasks

| ID | Task | Starting state | Success condition | Critical failure |
| --- | --- | --- | --- | --- |
| T-01 | Open or clone first Strategy | new account | correct Strategy workspace opens | blank canvas or wrong object |
| T-02 | Change one parameter | published Strategy with draft | new draft shows change; published version unchanged | live or published artifact mutates |
| T-03 | Run an interactive backtest | valid draft and data | result and assumptions appear | heavy-job behavior or hidden refusal |
| T-04 | Inspect assumptions | completed result | user finds data, costs, fill, warmup, and version facts | user trusts result without finding them |
| T-05 | Compare baseline and candidate | two exact results | user identifies material differences and evidence | comparison mixes unlike inputs |
| T-06 | Interpret OOS, walk-forward, and Monte Carlo | validation evidence | user describes each correctly | metric becomes a magic score |
| T-07 | Find stale data | one stale required input | user identifies source, age, and blocked effect | UI reports healthy |
| T-08 | Fix invalid node | one typed connection error | user locates and repairs exact port | generic graph failure |
| T-09 | Publish revision | clean valid draft | immutable revision created | draft and version confused |
| T-10 | Paper deploy | admitted candidate | exact binding appears in paper cockpit | broker or live authority implied |
| T-11 | Understand preflight refusal | missing provider capability | user states what is missing and next action | generic failed status |
| T-12 | Suspend and recover deployment | active paper deployment | no new entries while risk management stays available | positions become unmanaged |
| T-13 | Explain a trade | completed paper trade | user traces Strategy, data, signal, admission, intent, fill | only log text available |
| T-14 | Explain rejected candidate | simultaneous candidates | user identifies rank, capital, policy, and reason | rejection appears arbitrary |
| T-15 | Resolve capital contention | one fundable amount | user predicts deterministic winner and no resize | first-arrival or hidden resize |
| T-16 | Inspect degraded realtime state | browser connected, provider stale | user distinguishes transport and feed health | connected reads as healthy |
| T-17 | Edit a large graph | 300-node Strategy | find, edit, undo, and focus | pointer-only or unusable latency |
| T-18 | Recover accidental edit | deployed version plus dirty draft | undo draft without changing deployment | deployment meaning changes |
| T-19 | Inspect Universe result | V2 prototype only | user finds population, filters, rank, top-K, and time | screener result lacks evidence |
| T-20 | Inspect Workflow progress | V2 prototype only | user finds current step, retry, approval, and terminal reason | spinner with no durable state |

## Accessibility variants

Repeat T-02, T-08, T-09, T-11, T-17, and T-18:

- keyboard only;
- single-pointer without drag;
- 200 percent zoom;
- reduced motion;
- screen reader;
- high contrast;
- 390 by 844 where the task is allowed.

## Benchmark environments

1. Current production frontend against safe mock data.
2. Accepted standalone prototype with deterministic fixtures.
3. Future integrated frontend after canonical API wiring.

Do not compare completion time when the task is absent in one environment. Record absent.

## Evidence package

Each run should retain:

- build and frontend commit;
- task fixture version;
- viewport and input mode;
- recording or notes with consent;
- timings;
- errors and network log;
- participant interpretation;
- result table;
- observed failure;
- proposed correction;
- retest.

Do not retain private Strategy content.

## Acceptance gates

V1 core tasks T-01 through T-18 should have:

- at least 90 percent completion for allowed tasks;
- zero false-live or false-authority interpretations;
- zero accidental mutation of immutable or deployed objects;
- all refusals understood without developer explanation by the final retest;
- keyboard completion for graph material-change tasks;
- no page-level horizontal overflow at 390 pixels.

These targets are proposed. The owner may revise them after the first measured baseline.
