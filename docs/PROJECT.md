# Project record

## Objective

Coordinate agents through a shared blackboard: versioned JSON entries, knowledge sources triggered by key changes, deterministic priority scheduling, fault isolation and a goal check.

## Scope

- In scope: the public API in [README.md](../README.md): `Entry`, `Blackboard`, `BlackboardError`, `KnowledgeSource`, `Coordinator`, `RunReport`.
- In scope: JSON-compatible board values, versioned keys, declared source triggers and writes, deterministic single-threaded scheduling, bounded cycles and history, goal and quiescence termination, and failure isolation.
- Out of scope: concurrent execution, persistence, distributed boards, and async sources.

## Timeline

| Date | Event |
|---|---|
| 2026 | Repository created from the factory utility template. |

## Effort metrics

Measured values only; a value that has not been measured stays "pending measurement".

| Metric | Value |
|---|---|
| Tokens (input / output) | 805428 / 67833 |
| Hours (human) | pending measurement |
| Cost (USD) | 0.0968 |

## Factory run u223 (measured from API usage)

| Date (UTC) | Phase | Model | Batch | Input | Output | Cache write | Cache read | Cost (USD) |
|---|---|---|---|---|---|---|---|---|
| 2026-11-11 | generation | deepseek-v4-pro | yes | 1729 | 21128 | 0 | 3328 | 0.0430 |
| 2026-11-11 | fix-1 | deepseek-flash | no | 20924 | 13020 | 0 | 270336 | 0.0118 |
| 2026-11-11 | audit | deepseek-flash | no | 22409 | 25173 | 0 | 341248 | 0.0195 |
| 2026-11-11 | fix-2 | deepseek-flash | no | 8735 | 3041 | 0 | 29568 | 0.0032 |
| 2026-11-11 | docs | deepseek-flash | no | 106895 | 5471 | 0 | 256 | 0.0193 |

Total: $0.0968. Prices: deepseek line, as measured by its adapter. Providers serve the current version of each model id, so the date tells which version answered; versions, launch stages and price sources per line are in the factory's model register (docs/MODELS.md).
