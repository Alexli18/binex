"""Suite loader — loads and validates an eval YAML file into EvalSuite."""

from __future__ import annotations

import warnings
from pathlib import Path

import yaml
from pydantic import ValidationError

from binex.eval.models import EvalSuite


def load_suite(path: str | Path) -> EvalSuite:
    """Load and validate an eval suite YAML file.

    Path fields inside the suite are resolved relative to the suite file's
    directory, mirroring the convention in workflow_spec/loader.py.
    """
    path = Path(path)

    try:
        raw = path.read_text()
    except FileNotFoundError:
        raise

    try:
        data = yaml.safe_load(raw)
    except yaml.YAMLError as exc:
        raise ValueError(f"YAML parse error in '{path}': {exc}") from exc

    if not isinstance(data, dict):
        raise ValueError(f"Eval suite '{path}' must be a YAML mapping")

    # Enforce required top-level keys with actionable messages
    for key in ("name", "workflow", "cases"):
        if key not in data:
            raise ValueError(f"Eval suite missing required field '{key}'")

    # Resolve workflow path relative to suite directory
    workflow_raw = data["workflow"]
    workflow_path = Path(workflow_raw)
    if not workflow_path.is_absolute():
        workflow_path = path.parent / workflow_path
    if not workflow_path.exists():
        raise ValueError(f"Workflow not found: {workflow_path}")
    data["workflow"] = str(workflow_path)

    # Strip and warn about baseline_run_id in cases (ignored field)
    cases = data.get("cases") or []
    for case in cases:
        if isinstance(case, dict) and "baseline_run_id" in case:
            warnings.warn(
                f"'baseline_run_id' in case '{case.get('id', '?')}' is ignored "
                "(baselines are stored in SQLite via `binex eval bless`)",
                UserWarning,
                stacklevel=2,
            )
            del case["baseline_run_id"]

    # Convert unknown assert types to a clearer error before Pydantic sees them
    _check_assert_types(cases)

    try:
        suite = EvalSuite(**data)
    except ValidationError as exc:
        # Translate Pydantic errors into contract-specified messages
        raise ValueError(_format_validation_error(exc)) from exc

    return suite


def _check_assert_types(cases: list) -> None:
    """Raise a clear error for unknown assert types before Pydantic validation."""
    valid_types = {"contains", "not_contains", "regex", "json_path", "llm_judge"}
    for case in cases:
        if not isinstance(case, dict):
            continue
        for assert_dict in case.get("asserts") or []:
            if not isinstance(assert_dict, dict):
                continue
            t = assert_dict.get("type")
            if t is not None and t not in valid_types:
                raise ValueError(
                    f"Unknown assert type '{t}' "
                    f"(expected: {', '.join(sorted(valid_types))})"
                )


def _format_validation_error(exc: ValidationError) -> str:
    """Map Pydantic validation errors to contract-specified message shapes."""
    errors = exc.errors()
    if not errors:
        return str(exc)

    first = errors[0]
    loc = first.get("loc", ())
    msg = first.get("msg", "")

    # Handle "at least one case"
    if "at least one case" in msg:
        return msg

    # Duplicate case id (passed through from field_validator)
    if "Duplicate case id" in msg:
        return msg

    # Assert type-level errors — extract assert index if present
    if "requires" in msg and loc:
        return msg.replace("Value error, ", "")

    # Threshold range errors
    if "min_similarity" in msg or "max_cost_delta" in msg or "max_latency_delta_ms" in msg:
        return msg.replace("Value error, ", "")

    # Fallback
    return msg.replace("Value error, ", "")
