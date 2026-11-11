# Adopt blackboard pattern with deterministic priority scheduling and bounded state

Status: accepted (generated, pending human review)

## Context

Multi-agent systems that pass messages directly become hard to extend and debug. A blackboard decouples agents by letting them read/write shared state and react to changes in declared keys.

## Decision

Implement a synchronous blackboard coordinator with versioned JSON entries, knowledge sources that declare triggers and writes, deterministic scheduling by priority and name, fault isolation for exceptions and invalid writes, and bounded resources (entries, value size, cycles, history).

## Consequences

The library is easy to test and reason about because it is single-threaded and deterministic. Sources must be synchronous; asynchronous or distributed agents are out of scope. Invalid writes or exceptions disable the source for the remainder of the run, preventing cascading failures. Resource limits protect against unbounded growth. The choice of JSON round-trip deep copies ensures data isolation but limits value types to JSON-compatible ones.
