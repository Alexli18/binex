"""Workflow eval & regression testing.

Three capabilities:

* ``assertions`` — post-execution block-on checks declared per node in YAML.
  Evaluated by :mod:`binex.eval.node_assertions`, enforced by the orchestrator.
* ``binex eval golden`` — run a workflow and (optionally) compare it against a
  stored "golden" run using the diff engine, exiting non-zero on regressions
  (issue #60). Implemented by :mod:`binex.eval.golden`.
* ``binex eval run|bless|baselines`` — eval suites: named cases with asserts
  (contains/regex/json_path/llm_judge) compared against blessed baselines
  (feature 020). Implemented by :mod:`binex.eval.runner` and friends
  (:mod:`binex.eval.models`, :mod:`binex.eval.loader`, :mod:`binex.eval.suite_asserts`,
  :mod:`binex.eval.compare`).
"""

from __future__ import annotations

from binex.eval.node_assertions import (
    AssertionOutcome,
    evaluate_assertions,
)

__all__ = ["AssertionOutcome", "evaluate_assertions"]
