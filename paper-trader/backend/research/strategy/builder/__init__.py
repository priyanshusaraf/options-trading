"""Constrained primitive strategy builder (research plane).

The bot composes NEW strategies from a fixed vocabulary of vetted, unit-tested
primitive blocks, emits real Python source for each composition, statically validates
that source against a strict AST allow-list, loads it in a no-builtins sandbox, and
runs it through the exact same research gauntlet (qualify → validate → score) as any
hand-written strategy. Only a composition that clears every hard gate becomes a
human-reviewable PromotionCandidate — a generated strategy never reaches capital
except through the same explicit Approve→Deploy bridge.

Layers:
  blocks    — the primitive library: pure `df -> bool Series` predicates.
  grammar   — the declarative Composition spec + strict block-reference parsing.
  emit      — Composition -> readable `compute(df, **params)` Python source.
  validate  — AST allow-list: the static security boundary over emitted source.
  load      — validated source -> compiled compute in a no-builtins namespace -> Strategy.
  search    — bounded, economically-sensible enumeration of compositions.
"""
