"""Output schema validation for node results."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

import jsonschema

from binex.runtime.json_repair import repair_json_text


@dataclass
class ValidationResult:
    valid: bool
    errors: list[str] = field(default_factory=list)
    normalized: Any = None  # parsed value that was validated
    repaired: bool = False  # deterministic repair was applied to a string input


def validate_output(output: Any, schema: dict[str, Any]) -> ValidationResult:
    """Validate node output against a JSON Schema.

    Handles:
    - dict output: validate directly
    - string output: parse as JSON, applying deterministic repair on failure
    - None/empty: validation failure
    """
    repaired = False

    # Parse string to dict if needed
    if isinstance(output, str):
        try:
            output = json.loads(output)
        except (json.JSONDecodeError, TypeError):
            # Deterministic repair (0 tokens): strip fences / extract balanced JSON.
            repaired_text = repair_json_text(output)
            if repaired_text is None:
                return ValidationResult(
                    valid=False,
                    errors=[f"Output is not valid JSON: {output[:100]}"],
                )
            output = json.loads(repaired_text)
            repaired = True

    if output is None:
        return ValidationResult(valid=False, errors=["Output is None"])

    # Validate against schema
    validator_cls = jsonschema.validators.validator_for(schema)
    validator = validator_cls(schema)
    error_messages = [e.message for e in validator.iter_errors(output)]

    if error_messages:
        return ValidationResult(
            valid=False, errors=error_messages, normalized=output, repaired=repaired,
        )
    return ValidationResult(valid=True, normalized=output, repaired=repaired)
