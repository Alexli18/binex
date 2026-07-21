"""Workflow eval & regression testing (issue #60).

Two capabilities:

* ``assertions`` — post-execution block-on checks declared per node in YAML.
  Evaluated by :mod:`binex.eval.assertions`, enforced by the orchestrator.
* ``binex eval`` — run a workflow and (optionally) compare it against a stored
  "golden" run using the diff engine, exiting non-zero on regressions.
  Implemented by :mod:`binex.eval.runner`.
"""

from __future__ import annotations

from binex.eval.assertions import (
    AssertionOutcome,
    evaluate_assertions,
)

__all__ = ["AssertionOutcome", "evaluate_assertions"]
